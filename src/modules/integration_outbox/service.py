from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import IntegrationOutboxEvent
from .schemas import IntegrationEventEnvelope

_FORBIDDEN = {"authorization", "cookie", "password", "secret", "token", "api_key", "private_key", "credential"}

def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items() if str(k).lower() not in _FORBIDDEN}
    if isinstance(value, list): return [_safe(v) for v in value]
    return value

def stable_event_key(event_type: str, aggregate_type: str, aggregate_id: str, source_key: str) -> str:
    raw = json.dumps([event_type, aggregate_type, aggregate_id, source_key], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()

def enqueue_event(session: Session, *, event_type: str, aggregate_type: str, aggregate_id: str, source_key: str, tenant_id: str | None = None, data: dict[str, Any] | None = None) -> IntegrationOutboxEvent:
    key = stable_event_key(event_type, aggregate_type, aggregate_id, source_key)
    existing = session.scalar(select(IntegrationOutboxEvent).where(IntegrationOutboxEvent.event_key == key))
    if existing: return existing
    now = datetime.now(UTC)
    envelope = IntegrationEventEnvelope(event_key=key, event_type=event_type, tenant_id=tenant_id, aggregate_type=aggregate_type, aggregate_id=aggregate_id, occurred_at=now, data=_safe(data or {}))
    row = IntegrationOutboxEvent(event_key=key, event_type=event_type, tenant_id=tenant_id, aggregate_type=aggregate_type, aggregate_id=aggregate_id, envelope=envelope.model_dump(mode="json"))
    session.add(row); session.flush(); return row

def list_outbox(session: Session, *, tenant_id: str | None = None, event_type: str | None = None) -> list[IntegrationOutboxEvent]:
    q = select(IntegrationOutboxEvent).order_by(IntegrationOutboxEvent.created_at.asc(), IntegrationOutboxEvent.id.asc())
    if tenant_id is not None: q = q.where(IntegrationOutboxEvent.tenant_id == tenant_id)
    if event_type is not None: q = q.where(IntegrationOutboxEvent.event_type == event_type)
    return list(session.scalars(q))
