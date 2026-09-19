from __future__ import annotations

import argparse
import logging
import os
import socket
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Self

from src.shared.config.settings import get_settings
from src.shared.redis.errors import RedisUnavailableError
from src.shared.redis.queue import QueueDelivery, RedisStreamQueue
from src.tender_research.rag.job_runner import (
    _get_session,
    build_worker_queue,
    run_analyze_job,
    run_prepare_job,
)
from src.tender_research.rag.job_service import (
    fail_job,
    get_job,
    is_terminal_job_status,
    requeue_job,
    touch_job_heartbeat,
)

logger = logging.getLogger(__name__)


def default_consumer_name() -> str:
    host = socket.gethostname().strip() or "worker"
    return f"{host}-{os.getpid()}"


def _job_identity(delivery: QueueDelivery) -> tuple[str, dict]:
    payload = delivery.envelope.payload
    if not isinstance(payload, dict):
        raise TypeError("queue payload must be an object")
    job_id = str(payload.get("job_id") or delivery.envelope.run_id or "").strip()
    if not job_id:
        raise ValueError("queue payload job_id is required")
    if delivery.envelope.run_id and delivery.envelope.run_id != job_id:
        raise ValueError("queue payload job_id does not match envelope run_id")
    request = payload.get("request")
    if not isinstance(request, dict):
        raise TypeError("queue payload request must be an object")
    return job_id, request


def _load_job(job_id: str):
    session = _get_session()
    try:
        return get_job(session, job_id)
    finally:
        session.close()


def _mark_retry(job_id: str, attempt: int, max_attempts: int) -> None:
    session = _get_session()
    try:
        requeue_job(
            session,
            job_id,
            warning=f"worker retry scheduled: attempt {attempt + 1}/{max_attempts}",
        )
    finally:
        session.close()


def _mark_unsupported(job_id: str, job_type: str) -> None:
    session = _get_session()
    try:
        fail_job(
            session,
            job_id,
            errors=[f"unsupported worker job type: {job_type}"],
            current_step="worker_dispatch",
        )
    finally:
        session.close()


def _lease_heartbeat(queue: RedisStreamQueue, delivery: QueueDelivery, consumer_name: str) -> None:
    if not queue.touch(delivery, consumer_name):
        raise RedisUnavailableError("Redis queue lease refresh unavailable: category=lease_lost")


def _durable_heartbeat(job_id: str) -> None:
    session = _get_session()
    try:
        touch_job_heartbeat(session, job_id)
    finally:
        session.close()


def _job_is_stale(record: object, visibility_timeout_seconds: int) -> bool:
    updated_at = getattr(record, "updated_at", None)
    if updated_at is None:
        return True
    if updated_at.tzinfo is None or updated_at.tzinfo.utcoffset(updated_at) is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    age_seconds = (datetime.now(UTC) - updated_at.astimezone(UTC)).total_seconds()
    return age_seconds >= visibility_timeout_seconds


class _LeaseRenewer:
    def __init__(
        self,
        queue: RedisStreamQueue,
        delivery: QueueDelivery,
        consumer_name: str,
        job_id: str,
    ) -> None:
        self.queue = queue
        self.delivery = delivery
        self.consumer_name = consumer_name
        self.job_id = job_id
        self.interval_seconds = max(
            1.0,
            min(float(delivery.envelope.visibility_timeout_seconds) / 3.0, 30.0),
        )
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name=f"tender-worker-lease-{job_id}",
            daemon=True,
        )

    def pulse(self) -> None:
        _lease_heartbeat(self.queue, self.delivery, self.consumer_name)
        _durable_heartbeat(self.job_id)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self.pulse()
            except Exception:
                logger.exception("Worker lease heartbeat failed", extra={"job_id": self.job_id})

    def __enter__(self) -> Self:
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop.set()
        self._thread.join(timeout=self.interval_seconds + 1.0)


def process_delivery(
    queue: RedisStreamQueue,
    delivery: QueueDelivery,
    consumer_name: str,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> bool:
    """Process one at-least-once delivery and reconcile durable PostgreSQL state."""
    try:
        job_id, request = _job_identity(delivery)
    except (TypeError, ValueError):
        logger.warning("Dropping malformed worker delivery", extra={"stream_id": delivery.stream_id})
        queue.ack(delivery)
        return True

    record = _load_job(job_id)
    if record is None:
        logger.warning("Dropping worker delivery for missing job", extra={"job_id": job_id})
        queue.ack(delivery)
        return True
    if is_terminal_job_status(record.status):
        queue.ack(delivery)
        return True
    if delivery.reclaimed and record.status == "running":
        if not _job_is_stale(record, delivery.envelope.visibility_timeout_seconds):
            # A live worker may temporarily lose Redis ownership during
            # transport turbulence. Do not duplicate execution while the
            # durable PostgreSQL heartbeat is still fresh.
            queue.touch(delivery, consumer_name)
            return False
        if delivery.envelope.attempt >= delivery.envelope.max_attempts:
            session = _get_session()
            try:
                fail_job(
                    session,
                    job_id,
                    errors=["worker_lease_expired_after_max_attempts"],
                    current_step="worker_recovery",
                )
            finally:
                session.close()
            queue.ack(delivery)
            return True
        _, next_envelope = queue.retry(delivery)
        _mark_retry(job_id, next_envelope.attempt - 1, next_envelope.max_attempts)
        return True
    if record.status == "failed":
        if delivery.envelope.attempt >= delivery.envelope.max_attempts:
            queue.ack(delivery)
            return True
        if delivery.reclaimed:
            # The same attempt already ran and failed before it could publish
            # its bounded retry. Advance the delivery attempt instead of
            # re-running the same attempt after a worker crash.
            _, next_envelope = queue.retry(delivery)
            _mark_retry(job_id, next_envelope.attempt - 1, next_envelope.max_attempts)
            return True
        # A fresh retry delivery may observe the failed state left by the
        # previous attempt if the worker crashed after publishing the retry
        # but before resetting PostgreSQL to queued.
        _mark_retry(job_id, delivery.envelope.attempt - 1, delivery.envelope.max_attempts)

    if delivery.envelope.job_type not in {"prepare", "analyze"}:
        _mark_unsupported(job_id, delivery.envelope.job_type)
        queue.ack(delivery)
        return True

    with _LeaseRenewer(queue, delivery, consumer_name, job_id) as renewer:
        if delivery.envelope.job_type == "prepare":
            run_prepare_job(job_id, request, heartbeat=renewer.pulse)
        else:
            run_analyze_job(job_id, request, heartbeat=renewer.pulse)

    record = _load_job(job_id)
    if record is None:
        logger.warning("Job disappeared after worker execution", extra={"job_id": job_id})
        queue.ack(delivery)
        return True

    if record.status == "failed" and delivery.envelope.attempt < delivery.envelope.max_attempts:
        settings = get_settings()
        delay = min(
            settings.tender_research_worker_retry_backoff_seconds
            * (2 ** max(delivery.envelope.attempt - 1, 0)),
            300,
        )
        if delay:
            sleep_fn(float(delay))
        _, next_envelope = queue.retry(delivery)
        _mark_retry(job_id, next_envelope.attempt - 1, next_envelope.max_attempts)
        return True

    if is_terminal_job_status(record.status) or record.status == "failed":
        queue.ack(delivery)
        return True

    logger.warning(
        "Worker execution returned a non-terminal job; leaving delivery pending for recovery",
        extra={"job_id": job_id, "status": record.status},
    )
    return False


def run_once(
    *,
    queue: RedisStreamQueue | None = None,
    consumer_name: str | None = None,
    block_ms: int = 1000,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> bool:
    settings = get_settings()
    if settings.tender_research_job_backend.strip().lower() != "redis":
        raise RuntimeError("Tender research worker requires ARVECTUM_TENDER_RESEARCH_JOB_BACKEND=redis")
    worker_queue = queue or build_worker_queue()
    consumer = consumer_name or default_consumer_name()
    delivery = worker_queue.receive(consumer, block_ms=block_ms)
    if delivery is None:
        return False
    return process_delivery(worker_queue, delivery, consumer, sleep_fn=sleep_fn)


def run_forever(*, consumer_name: str | None = None, block_ms: int = 1000) -> None:
    queue = build_worker_queue()
    consumer = consumer_name or default_consumer_name()
    logger.info("Tender analysis worker started", extra={"consumer": consumer})
    while True:
        run_once(queue=queue, consumer_name=consumer, block_ms=block_ms)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the durable Tender Agent analysis worker")
    parser.add_argument("--once", action="store_true", help="Process at most one queue delivery and exit")
    parser.add_argument("--consumer", default=None, help="Explicit Redis consumer name")
    parser.add_argument("--block-ms", type=int, default=1000, help="Redis stream blocking read timeout in milliseconds")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.once:
            run_once(consumer_name=args.consumer, block_ms=args.block_ms)
        else:
            run_forever(consumer_name=args.consumer, block_ms=args.block_ms)
    except KeyboardInterrupt:
        return 0
    except (RedisUnavailableError, RuntimeError, ValueError) as exc:
        logger.error("Tender analysis worker stopped: %s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
