from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import redis as redis_py
from src.shared.config.settings import get_settings
from src.shared.redis.client import require_client
from src.shared.redis.errors import RedisUnavailableError, redis_error_category
from src.shared.redis.keys import build_key


@dataclass
class QueueEnvelope:
    version: int = 1
    queue_name: str = ""
    message_id: str = ""
    job_type: str = ""
    deduplication_key: str = ""
    tenant: str = ""
    customer_id: str = ""
    project_id: str = ""
    procurement_case_id: str = ""
    run_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    enqueued_at: str = ""
    attempt: int = 1
    max_attempts: int = 3
    visibility_timeout_seconds: int = 300
    correlation_id: str = ""

    MAX_PAYLOAD_BYTES = 65536

    def validate(self) -> None:
        if not self.queue_name:
            raise ValueError("queue_name is required")
        if not self.message_id:
            raise ValueError("message_id is required")
        if not self.job_type:
            raise ValueError("job_type is required")
        if not self.tenant:
            raise ValueError("tenant is required")
        if not self.customer_id:
            raise ValueError("customer_id is required")
        if self.attempt < 1:
            raise ValueError("attempt must be >= 1")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.attempt > self.max_attempts:
            raise ValueError("attempt must be <= max_attempts")
        if self.visibility_timeout_seconds < 1:
            raise ValueError("visibility_timeout_seconds must be >= 1")
        raw = self._raw_payload_bytes()
        if len(raw) > self.MAX_PAYLOAD_BYTES:
            raise ValueError(f"payload exceeds {self.MAX_PAYLOAD_BYTES} bytes ({len(raw)})")

    def _raw_payload_bytes(self) -> bytes:
        return json.dumps(self.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "queue_name": self.queue_name,
            "message_id": self.message_id,
            "job_type": self.job_type,
            "deduplication_key": self.deduplication_key,
            "tenant": self.tenant,
            "customer_id": self.customer_id,
            "project_id": self.project_id,
            "procurement_case_id": self.procurement_case_id,
            "run_id": self.run_id,
            "payload": self.payload,
            "enqueued_at": self.enqueued_at or datetime.now(UTC).isoformat(),
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "visibility_timeout_seconds": self.visibility_timeout_seconds,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> QueueEnvelope:
        envelope = cls(
            version=int(value.get("version", 1)),
            queue_name=str(value.get("queue_name") or ""),
            message_id=str(value.get("message_id") or ""),
            job_type=str(value.get("job_type") or ""),
            deduplication_key=str(value.get("deduplication_key") or ""),
            tenant=str(value.get("tenant") or ""),
            customer_id=str(value.get("customer_id") or ""),
            project_id=str(value.get("project_id") or ""),
            procurement_case_id=str(value.get("procurement_case_id") or ""),
            run_id=str(value.get("run_id") or ""),
            payload=value.get("payload") if isinstance(value.get("payload"), dict) else {},
            enqueued_at=str(value.get("enqueued_at") or ""),
            attempt=int(value.get("attempt", 1)),
            max_attempts=int(value.get("max_attempts", 3)),
            visibility_timeout_seconds=int(value.get("visibility_timeout_seconds", 300)),
            correlation_id=str(value.get("correlation_id") or ""),
        )
        envelope.validate()
        return envelope

    def next_attempt(self) -> QueueEnvelope:
        if self.attempt >= self.max_attempts:
            raise ValueError("maximum attempts exhausted")
        return replace(
            self,
            message_id=uuid4().hex,
            enqueued_at="",
            attempt=self.attempt + 1,
        )


@dataclass(frozen=True)
class QueueDelivery:
    stream_id: str
    envelope: QueueEnvelope
    reclaimed: bool = False


class RedisStreamQueue:
    """Durable Redis Streams transport for ARV-008 workers.

    PostgreSQL remains the job source of truth. Redis owns only delivery,
    consumer-group lease state and bounded retry transport.
    """

    FIELD_NAME = "envelope"
    DEFAULT_GROUP = "tender-workers"
    DEFAULT_VISIBILITY_TIMEOUT_SECONDS = 300

    def __init__(
        self,
        queue_name: str,
        *,
        group_name: str = DEFAULT_GROUP,
        namespace: str | None = None,
        environment: str | None = None,
        visibility_timeout_seconds: int = DEFAULT_VISIBILITY_TIMEOUT_SECONDS,
        client: redis_py.Redis | None = None,
    ) -> None:
        if not queue_name.strip():
            raise ValueError("queue_name is required")
        if not group_name.strip():
            raise ValueError("group_name is required")
        if visibility_timeout_seconds < 1:
            raise ValueError("visibility_timeout_seconds must be >= 1")

        settings = get_settings()
        self.queue_name = queue_name.strip()
        self.group_name = group_name.strip()
        self.visibility_timeout_seconds = int(visibility_timeout_seconds)
        self._client = client or require_client()
        effective_namespace = namespace or settings.arvectum_redis_namespace
        effective_environment = environment or settings.arvectum_redis_environment
        self.stream_key = build_key(
            namespace=effective_namespace,
            environment=effective_environment,
            component="queue",
            dimension=self.queue_name,
        )

    def _raise_unavailable(self, operation: str, exc: Exception) -> None:
        category = redis_error_category(exc)
        raise RedisUnavailableError(f"Redis queue {operation} unavailable: category={category}") from None

    def ensure_group(self) -> None:
        try:
            self._client.xgroup_create(
                name=self.stream_key,
                groupname=self.group_name,
                id="0",
                mkstream=True,
            )
        except redis_py.ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                return
            self._raise_unavailable("group_create", exc)
        except redis_py.RedisError as exc:
            self._raise_unavailable("group_create", exc)

    def enqueue(self, envelope: QueueEnvelope) -> str:
        envelope.validate()
        if envelope.queue_name != self.queue_name:
            raise ValueError("envelope queue_name does not match transport queue")
        payload = json.dumps(envelope.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        try:
            # Never trim the stream on enqueue: Redis MAXLEN can remove
            # entries that are still pending in a consumer group. Acknowledged
            # entries are deleted explicitly instead.
            stream_id = self._client.xadd(
                self.stream_key,
                {self.FIELD_NAME: payload},
            )
        except redis_py.RedisError as exc:
            self._raise_unavailable("enqueue", exc)
        return str(stream_id)

    def _parse_message(self, stream_id: str, fields: dict[str, Any], *, reclaimed: bool) -> QueueDelivery:
        raw = fields.get(self.FIELD_NAME)
        if not isinstance(raw, str):
            raise TypeError("queue message envelope field is missing")
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            raise TypeError("queue message envelope is invalid")
        envelope = QueueEnvelope.from_dict(loaded)
        if envelope.queue_name != self.queue_name:
            raise ValueError("queue message belongs to another queue")
        return QueueDelivery(stream_id=str(stream_id), envelope=envelope, reclaimed=reclaimed)

    def reclaim_stale(self, consumer_name: str) -> QueueDelivery | None:
        self.ensure_group()
        try:
            result = self._client.xautoclaim(
                self.stream_key,
                self.group_name,
                consumer_name,
                min_idle_time=self.visibility_timeout_seconds * 1000,
                start_id="0-0",
                count=1,
            )
        except redis_py.RedisError as exc:
            self._raise_unavailable("reclaim", exc)
        messages = result[1] if isinstance(result, (list, tuple)) and len(result) >= 2 else []
        if not messages:
            return None
        stream_id, fields = messages[0]
        return self._parse_message(stream_id, fields, reclaimed=True)

    def receive(self, consumer_name: str, *, block_ms: int = 1000) -> QueueDelivery | None:
        if not consumer_name.strip():
            raise ValueError("consumer_name is required")
        if block_ms < 0:
            raise ValueError("block_ms must be >= 0")
        reclaimed = self.reclaim_stale(consumer_name)
        if reclaimed is not None:
            return reclaimed
        kwargs: dict[str, Any] = {
            "groupname": self.group_name,
            "consumername": consumer_name,
            "streams": {self.stream_key: ">"},
            "count": 1,
        }
        if block_ms:
            kwargs["block"] = block_ms
        try:
            response = self._client.xreadgroup(**kwargs)
        except redis_py.RedisError as exc:
            self._raise_unavailable("receive", exc)
        if not response:
            return None
        _, messages = response[0]
        if not messages:
            return None
        stream_id, fields = messages[0]
        return self._parse_message(stream_id, fields, reclaimed=False)

    def touch(self, delivery: QueueDelivery, consumer_name: str) -> bool:
        try:
            claimed = self._client.xclaim(
                self.stream_key,
                self.group_name,
                consumer_name,
                min_idle_time=0,
                message_ids=[delivery.stream_id],
            )
        except redis_py.RedisError as exc:
            self._raise_unavailable("lease_refresh", exc)
        return bool(claimed)

    def retry(self, delivery: QueueDelivery) -> tuple[str, QueueEnvelope]:
        """Atomically publish the next attempt and acknowledge the current delivery."""
        next_envelope = delivery.envelope.next_attempt()
        payload = json.dumps(
            next_envelope.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            pipeline = self._client.pipeline(transaction=True)
            pipeline.xadd(
                self.stream_key,
                {self.FIELD_NAME: payload},
            )
            pipeline.xack(self.stream_key, self.group_name, delivery.stream_id)
            pipeline.xdel(self.stream_key, delivery.stream_id)
            result = pipeline.execute()
        except redis_py.RedisError as exc:
            self._raise_unavailable("retry", exc)
        if len(result) != 3 or not result[1]:
            raise RedisUnavailableError("Redis queue retry unavailable: category=protocol_error")
        return str(result[0]), next_envelope

    def ack(self, delivery: QueueDelivery) -> bool:
        try:
            pipeline = self._client.pipeline(transaction=True)
            pipeline.xack(self.stream_key, self.group_name, delivery.stream_id)
            pipeline.xdel(self.stream_key, delivery.stream_id)
            result = pipeline.execute()
        except redis_py.RedisError as exc:
            self._raise_unavailable("ack", exc)
        if len(result) != 2:
            raise RedisUnavailableError("Redis queue ack unavailable: category=protocol_error")
        return bool(result[0])
