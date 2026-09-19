from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.shared.redis.queue import QueueEnvelope


class TestQueueEnvelopeValidation:
    def test_valid_envelope(self):
        envelope = QueueEnvelope(
            queue_name="analysis",
            message_id=uuid4().hex,
            job_type="analyze",
            tenant="tenant_a",
            customer_id="cust_1",
            project_id="proj_1",
            procurement_case_id="case_1",
            run_id="run_1",
            payload={"key": "value"},
            enqueued_at=datetime.now(UTC).isoformat(),
            deduplication_key=uuid4().hex,
        )
        envelope.validate()

    def test_missing_queue_name_raises(self):
        envelope = QueueEnvelope(message_id="m1", job_type="j", tenant="t", customer_id="c")
        with pytest.raises(ValueError, match="queue_name"):
            envelope.validate()

    def test_missing_message_id_raises(self):
        envelope = QueueEnvelope(queue_name="q", job_type="j", tenant="t", customer_id="c")
        with pytest.raises(ValueError, match="message_id"):
            envelope.validate()

    def test_missing_job_type_raises(self):
        envelope = QueueEnvelope(queue_name="q", message_id="m1", tenant="t", customer_id="c")
        with pytest.raises(ValueError, match="job_type"):
            envelope.validate()

    def test_missing_tenant_raises(self):
        envelope = QueueEnvelope(queue_name="q", message_id="m1", job_type="j", customer_id="c")
        with pytest.raises(ValueError, match="tenant"):
            envelope.validate()

    def test_missing_customer_raises(self):
        envelope = QueueEnvelope(queue_name="q", message_id="m1", job_type="j", tenant="t")
        with pytest.raises(ValueError, match="customer_id"):
            envelope.validate()

    def test_payload_size_limit(self):
        envelope = QueueEnvelope(
            queue_name="q", message_id="m1", job_type="j", tenant="t", customer_id="c",
            payload={"data": "x" * 70000},
        )
        with pytest.raises(ValueError, match="payload exceeds"):
            envelope.validate()

    def test_versioned_schema(self):
        envelope = QueueEnvelope(
            queue_name="q", message_id="m1", job_type="j", tenant="t", customer_id="c"
        )
        assert envelope.version == 1

    def test_tenant_dimensions(self):
        envelope = QueueEnvelope(
            queue_name="q", message_id="m1", job_type="j", tenant="t1",
            customer_id="c1", project_id="p1", procurement_case_id="case1", run_id="r1",
        )
        assert envelope.tenant == "t1"
        assert envelope.customer_id == "c1"
        assert envelope.project_id == "p1"

    def test_retry_metadata(self):
        envelope = QueueEnvelope(
            queue_name="q", message_id="m1", job_type="j", tenant="t", customer_id="c",
            attempt=1, max_attempts=3, visibility_timeout_seconds=300,
        )
        assert envelope.attempt == 1
        assert envelope.max_attempts == 3
        assert envelope.visibility_timeout_seconds == 300

    def test_to_dict(self):
        envelope = QueueEnvelope(
            queue_name="q", message_id="m1", job_type="j", tenant="t", customer_id="c",
        )
        d = envelope.to_dict()
        assert d["queue_name"] == "q"
        assert d["version"] == 1
        assert d["job_type"] == "j"
        assert "enqueued_at" in d


class FakeStreamRedis:
    def __init__(self):
        self.groups: set[tuple[str, str]] = set()
        self.messages: list[tuple[str, dict[str, str]]] = []
        self.pending: list[tuple[str, dict[str, str]]] = []
        self.claimed: list[str] = []
        self.acked: list[str] = []
        self.deleted: list[str] = []

    def xgroup_create(self, *, name, groupname, id, mkstream):
        import redis as redis_py

        key = (name, groupname)
        if key in self.groups:
            raise redis_py.ResponseError("BUSYGROUP Consumer Group name already exists")
        self.groups.add(key)
        return True

    def xadd(self, name, fields, maxlen=None, approximate=None):
        stream_id = f"{len(self.messages) + len(self.pending) + 1}-0"
        self.messages.append((stream_id, fields))
        return stream_id

    def xautoclaim(self, name, groupname, consumername, min_idle_time, start_id, count):
        if not self.pending:
            return ["0-0", []]
        return ["0-0", [self.pending.pop(0)]]

    def xreadgroup(self, **kwargs):
        if not self.messages:
            return []
        item = self.messages.pop(0)
        self.pending.append(item)
        stream_name = next(iter(kwargs["streams"]))
        return [(stream_name, [item])]

    def xclaim(self, name, groupname, consumername, min_idle_time, message_ids):
        self.claimed.extend(message_ids)
        return [(message_ids[0], {})]

    def xack(self, name, groupname, stream_id):
        self.acked.append(stream_id)
        self.pending = [item for item in self.pending if item[0] != stream_id]
        return 1

    def xdel(self, name, stream_id):
        self.deleted.append(stream_id)
        self.messages = [item for item in self.messages if item[0] != stream_id]
        self.pending = [item for item in self.pending if item[0] != stream_id]
        return 1

    def pipeline(self, transaction=True):
        client = self

        class FakePipeline:
            def __init__(self):
                self.operations = []

            def xadd(self, name, fields, maxlen=None, approximate=None):
                self.operations.append(("xadd", name, fields, maxlen, approximate))
                return self

            def xack(self, name, groupname, stream_id):
                self.operations.append(("xack", name, groupname, stream_id))
                return self

            def xdel(self, name, stream_id):
                self.operations.append(("xdel", name, stream_id))
                return self

            def execute(self):
                results = []
                for operation in self.operations:
                    if operation[0] == "xadd":
                        _, name, fields, maxlen, approximate = operation
                        results.append(client.xadd(name, fields, maxlen=maxlen, approximate=approximate))
                    elif operation[0] == "xack":
                        _, name, groupname, stream_id = operation
                        results.append(client.xack(name, groupname, stream_id))
                    else:
                        _, name, stream_id = operation
                        results.append(client.xdel(name, stream_id))
                return results

        return FakePipeline()


class TestRedisStreamQueue:
    def _envelope(self):
        return QueueEnvelope(
            queue_name="analysis",
            message_id="message-1",
            job_type="analyze",
            tenant="tenant-a",
            customer_id="customer-a",
            run_id="job-1",
            payload={"job_id": "job-1"},
            attempt=1,
            max_attempts=3,
        )

    def _queue(self, client):
        from src.shared.redis.queue import RedisStreamQueue

        return RedisStreamQueue(
            "analysis",
            group_name="workers",
            namespace="test-arv008",
            environment="unit",
            client=client,
        )

    def test_round_trip_and_retry_metadata(self):
        envelope = self._envelope()

        restored = QueueEnvelope.from_dict(envelope.to_dict())
        retry = envelope.next_attempt()

        assert restored.queue_name == envelope.queue_name
        assert restored.message_id == envelope.message_id
        assert restored.payload == envelope.payload
        assert restored.enqueued_at
        assert retry.attempt == 2
        assert retry.max_attempts == 3
        assert retry.message_id != envelope.message_id

    def test_receive_ack_and_touch(self):
        client = FakeStreamRedis()
        queue = self._queue(client)
        stream_id = queue.enqueue(self._envelope())

        delivery = queue.receive("worker-1", block_ms=0)

        assert delivery is not None
        assert delivery.stream_id == stream_id
        assert delivery.envelope.run_id == "job-1"
        assert delivery.reclaimed is False
        assert queue.touch(delivery, "worker-1") is True
        assert client.claimed == [stream_id]
        assert queue.ack(delivery) is True
        assert client.acked == [stream_id]
        assert client.deleted == [stream_id]

    def test_reclaims_pending_before_new_delivery(self):
        client = FakeStreamRedis()
        queue = self._queue(client)
        old = self._envelope()
        old.message_id = "old-message"
        new = self._envelope()
        new.message_id = "new-message"

        old_id = queue.enqueue(old)
        first = queue.receive("worker-old", block_ms=0)
        assert first is not None and first.stream_id == old_id
        new_id = queue.enqueue(new)

        recovered = queue.receive("worker-restart", block_ms=0)

        assert recovered is not None
        assert recovered.stream_id == old_id
        assert recovered.reclaimed is True
        assert new_id != old_id

    def test_retry_atomically_requeues_next_attempt_and_acks_current(self):
        client = FakeStreamRedis()
        queue = self._queue(client)
        first_id = queue.enqueue(self._envelope())
        delivery = queue.receive("worker-1", block_ms=0)
        assert delivery is not None and delivery.stream_id == first_id

        retry_id, retry_envelope = queue.retry(delivery)

        assert retry_envelope.attempt == 2
        assert retry_envelope.message_id != delivery.envelope.message_id
        assert first_id in client.acked
        assert first_id in client.deleted
        assert retry_id != first_id

    def test_queue_name_mismatch_fails_closed(self):
        queue = self._queue(FakeStreamRedis())
        envelope = self._envelope()
        envelope.queue_name = "other"

        with pytest.raises(ValueError, match="does not match"):
            queue.enqueue(envelope)

    def test_retry_exhaustion_fails_closed(self):
        envelope = self._envelope()
        envelope.attempt = envelope.max_attempts

        with pytest.raises(ValueError, match="maximum attempts exhausted"):
            envelope.next_attempt()
