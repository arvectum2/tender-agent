from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class IntegrationEventEnvelope(BaseModel):
    schema_version: Literal["integration-event-v1"] = "integration-event-v1"
    event_key: str
    event_type: Literal["analysis_completed", "monitoring_alert", "review_required"]
    tenant_id: str | None = None
    aggregate_type: str
    aggregate_id: str
    occurred_at: datetime
    data: dict[str, Any]

class IntegrationOutboxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    event_key: str
    event_type: str
    tenant_id: str | None
    aggregate_type: str
    aggregate_id: str
    envelope: dict
    created_at: datetime

class AdapterStatus(BaseModel):
    enabled: Literal[False] = False
    mode: Literal["disabled"] = "disabled"
    reason: str = "Live external delivery requires a separate REVIEW/HUMAN gate."
