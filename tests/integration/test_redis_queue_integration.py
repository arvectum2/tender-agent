from __future__ import annotations

from uuid import uuid4

import pytest

from src.shared.redis.client import require_client
from src.shared.redis.queue import QueueEnvelope, RedisStreamQueue

pytestmark = pytest.mark.redis


def _queue(test_namespace: str, *, visibility_timeout_seconds: int = 300) -> RedisStreamQueue:
    return RedisStreamQueue(
        "analysis",
        group_name="arv008-workers",
        namespace=test_namespace,
        environment="integration",
        visibility_timeout_seconds=visibility_timeout_seconds,
        client=require_client(),
    )


def _envelope(*, attempt: int = 1, max_attempts: int = 3) -> QueueEnvelope:
    return QueueEnvelope(
        queue_name="analysis",
        message_id=uuid4().hex,
        job_type="analyze",
        tenant="tenant-a",
        customer_id="customer-a",
        run_id="job-a",
        payload={
            "job_id": "job-a",
            "request": {"registry_number": "0848300045426000620"},
        },
        attempt=attempt,
        max_attempts=max_attempts,
        visibility_timeout_seconds=300,
    )


def test_stream_queue_round_trip_and_ack(test_namespace, cleanup_keys):
    queue = _queue(test_namespace)
    stream_id = queue.enqueue(_envelope())

    delivery = queue.receive("worker-a", block_ms=0)

    assert delivery is not None
    assert delivery.stream_id == stream_id
    assert delivery.envelope.run_id == "job-a"
    assert delivery.envelope.payload["job_id"] == "job-a"
    assert delivery.reclaimed is False
    assert queue.ack(delivery) is True


def test_stream_queue_reclaims_stale_pending_delivery(test_namespace, cleanup_keys):
    queue = _queue(test_namespace, visibility_timeout_seconds=1)
    client = require_client()
    stream_id = queue.enqueue(_envelope())
    original = queue.receive("worker-old", block_ms=0)
    assert original is not None

    # Redis supports setting an explicit idle duration on XCLAIM. This makes the
    # restart-recovery test deterministic without a wall-clock sleep.
    claimed = client.xclaim(
        queue.stream_key,
        queue.group_name,
        "worker-old",
        min_idle_time=0,
        message_ids=[stream_id],
        idle=2000,
    )
    assert claimed

    recovered = queue.receive("worker-new", block_ms=0)

    assert recovered is not None
    assert recovered.stream_id == stream_id
    assert recovered.reclaimed is True
    assert queue.ack(recovered) is True


def test_stream_queue_retry_increments_attempt_and_acks_old_delivery(test_namespace, cleanup_keys):
    queue = _queue(test_namespace)
    first_id = queue.enqueue(_envelope())
    delivery = queue.receive("worker-a", block_ms=0)
    assert delivery is not None

    retry_id, retry_envelope = queue.retry(delivery)

    assert retry_id != first_id
    assert retry_envelope.attempt == 2
    assert retry_envelope.message_id != delivery.envelope.message_id

    retried = queue.receive("worker-b", block_ms=0)
    assert retried is not None
    assert retried.stream_id == retry_id
    assert retried.envelope.attempt == 2
    assert queue.ack(retried) is True
