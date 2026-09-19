from __future__ import annotations

import argparse
import logging
import os
import socket
import time
from collections.abc import Callable

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

    heartbeat = lambda: _lease_heartbeat(queue, delivery, consumer_name)
    if delivery.envelope.job_type == "prepare":
        run_prepare_job(job_id, request, heartbeat=heartbeat)
    elif delivery.envelope.job_type == "analyze":
        run_analyze_job(job_id, request, heartbeat=heartbeat)
    else:
        _mark_unsupported(job_id, delivery.envelope.job_type)
        queue.ack(delivery)
        return True

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
