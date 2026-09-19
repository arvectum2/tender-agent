from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from src.shared.redis.queue import QueueDelivery, QueueEnvelope
from src.tender_research.rag import worker
from src.tender_research.rag.job_schemas import TenderAnalysisJobRecord


def _delivery(
    *,
    job_type: str = "analyze",
    attempt: int = 1,
    max_attempts: int = 3,
    reclaimed: bool = False,
) -> QueueDelivery:
    envelope = QueueEnvelope(
        queue_name="tender-analysis",
        message_id=f"message-{attempt}",
        job_type=job_type,
        tenant="internal",
        customer_id="tender-research",
        run_id="job-1",
        payload={"job_id": "job-1", "request": {"registry_number": "0848300045426000620"}},
        attempt=attempt,
        max_attempts=max_attempts,
    )
    return QueueDelivery(stream_id=f"{attempt}-0", envelope=envelope, reclaimed=reclaimed)


def _record(status: str, *, updated_at: datetime | None = None) -> TenderAnalysisJobRecord:
    return TenderAnalysisJobRecord(
        id="job-1",
        job_type="analyze",
        registry_number="0848300045426000620",
        status=status,
        updated_at=updated_at,
    )


class FakeQueue:
    def __init__(self, delivery: QueueDelivery | None = None):
        self.delivery = delivery
        self.acked: list[str] = []
        self.touched: list[str] = []
        self.retried: list[str] = []

    def receive(self, consumer_name: str, *, block_ms: int = 1000):
        return self.delivery

    def touch(self, delivery: QueueDelivery, consumer_name: str) -> bool:
        self.touched.append(delivery.stream_id)
        return True

    def ack(self, delivery: QueueDelivery) -> bool:
        self.acked.append(delivery.stream_id)
        return True

    def retry(self, delivery: QueueDelivery):
        self.retried.append(delivery.stream_id)
        retry = delivery.envelope.next_attempt()
        return "retry-0", retry


def test_completed_delivery_is_acked_without_reexecution():
    queue = FakeQueue(_delivery())
    with patch.object(worker, "_load_job", return_value=_record("completed")), patch.object(
        worker, "run_analyze_job"
    ) as runner:
        processed = worker.process_delivery(queue, queue.delivery, "worker-1")

    assert processed is True
    assert queue.acked == ["1-0"]
    runner.assert_not_called()


def test_analyze_delivery_runs_with_lease_heartbeat_and_acks():
    queue = FakeQueue(_delivery())
    with patch.object(worker, "_load_job", side_effect=[_record("queued"), _record("completed")]), patch.object(
        worker, "run_analyze_job"
    ) as runner:
        processed = worker.process_delivery(queue, queue.delivery, "worker-1")

        heartbeat = runner.call_args.kwargs["heartbeat"]
        heartbeat()

    assert processed is True
    assert runner.call_args.args[:2] == ("job-1", {"registry_number": "0848300045426000620"})
    assert queue.touched == ["1-0"]
    assert queue.acked == ["1-0"]


def test_failed_delivery_is_requeued_with_bounded_retry():
    queue = FakeQueue(_delivery(attempt=1, max_attempts=3))
    settings = SimpleNamespace(tender_research_worker_retry_backoff_seconds=0)
    with patch.object(worker, "_load_job", side_effect=[_record("queued"), _record("failed")]), patch.object(
        worker, "run_analyze_job"
    ), patch.object(worker, "_mark_retry") as mark_retry, patch.object(
        worker, "get_settings", return_value=settings
    ):
        processed = worker.process_delivery(queue, queue.delivery, "worker-1", sleep_fn=lambda _: None)

    assert processed is True
    mark_retry.assert_called_once_with("job-1", 1, 3)
    assert queue.retried == ["1-0"]
    assert queue.acked == []


def test_exhausted_failed_delivery_is_acked_without_retry():
    queue = FakeQueue(_delivery(attempt=3, max_attempts=3))
    with patch.object(worker, "_load_job", return_value=_record("failed")), patch.object(
        worker, "_mark_retry"
    ) as mark_retry:
        processed = worker.process_delivery(queue, queue.delivery, "worker-1")

    assert processed is True
    mark_retry.assert_not_called()
    assert queue.retried == []
    assert queue.acked == ["3-0"]


def test_unsupported_job_type_fails_job_and_acks():
    queue = FakeQueue(_delivery(job_type="unsupported"))
    with patch.object(worker, "_load_job", return_value=_record("queued")), patch.object(
        worker, "_mark_unsupported"
    ) as mark_unsupported:
        processed = worker.process_delivery(queue, queue.delivery, "worker-1")

    assert processed is True
    mark_unsupported.assert_called_once_with("job-1", "unsupported")
    assert queue.acked == ["1-0"]


def test_run_once_requires_explicit_redis_backend():
    queue = FakeQueue()
    settings = SimpleNamespace(tender_research_job_backend="thread")
    with patch.object(worker, "get_settings", return_value=settings):
        try:
            worker.run_once(queue=queue, consumer_name="worker-1", block_ms=0)
        except RuntimeError as exc:
            assert "requires" in str(exc)
        else:
            raise AssertionError("thread backend must not start redis worker")


def test_fresh_retry_delivery_requeues_failed_job_before_execution():
    queue = FakeQueue(_delivery(attempt=2, max_attempts=3))
    with patch.object(worker, "_load_job", side_effect=[_record("failed"), _record("completed")]), patch.object(
        worker, "_mark_retry"
    ) as mark_retry, patch.object(worker, "run_analyze_job") as runner:
        processed = worker.process_delivery(queue, queue.delivery, "worker-restart")

    assert processed is True
    mark_retry.assert_called_once_with("job-1", 1, 3)
    runner.assert_called_once()
    assert queue.acked == ["2-0"]


def test_reclaimed_failed_delivery_advances_attempt_without_rerunning_same_attempt():
    queue = FakeQueue(_delivery(attempt=1, max_attempts=3, reclaimed=True))
    with patch.object(worker, "_load_job", return_value=_record("failed")), patch.object(
        worker, "_mark_retry"
    ) as mark_retry, patch.object(worker, "run_analyze_job") as runner:
        processed = worker.process_delivery(queue, queue.delivery, "worker-restart")

    assert processed is True
    runner.assert_not_called()
    assert queue.retried == ["1-0"]
    mark_retry.assert_called_once_with("job-1", 1, 3)


def test_reclaimed_running_delivery_with_fresh_postgres_heartbeat_does_not_duplicate_execution():
    queue = FakeQueue(_delivery(attempt=1, max_attempts=3, reclaimed=True))
    record = _record("running", updated_at=datetime.now(UTC))
    with patch.object(worker, "_load_job", return_value=record), patch.object(
        worker, "run_analyze_job"
    ) as runner:
        processed = worker.process_delivery(queue, queue.delivery, "worker-recovery")

    assert processed is False
    runner.assert_not_called()
    assert queue.touched == ["1-0"]
    assert queue.retried == []
    assert queue.acked == []


def test_reclaimed_running_delivery_with_stale_postgres_heartbeat_advances_retry():
    queue = FakeQueue(_delivery(attempt=1, max_attempts=3, reclaimed=True))
    stale = datetime.now(UTC) - timedelta(seconds=301)
    record = _record("running", updated_at=stale)
    with patch.object(worker, "_load_job", return_value=record), patch.object(
        worker, "_mark_retry"
    ) as mark_retry, patch.object(worker, "run_analyze_job") as runner:
        processed = worker.process_delivery(queue, queue.delivery, "worker-recovery")

    assert processed is True
    runner.assert_not_called()
    assert queue.retried == ["1-0"]
    mark_retry.assert_called_once_with("job-1", 1, 3)
