from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

MONITORING_CONTRACT_VERSION = "1.0"


class WatchTarget(BaseModel):
    contract_version: str = MONITORING_CONTRACT_VERSION
    source: str
    external_id: str
    source_url: str | None = None
    saved_search: dict[str, Any] | None = None


class DocumentState(BaseModel):
    source_document_id: str
    sha256: str | None = None
    revision: str | None = None
    source_url: str | None = None


class SourceSnapshot(BaseModel):
    contract_version: str = MONITORING_CONTRACT_VERSION
    source: str
    external_id: str
    source_url: str | None = None
    application_deadline: datetime | None = None
    nmck_amount: Decimal | None = None
    status: str | None = None
    notice_revision: str | None = None
    cancelled: bool | None = None
    documents: list[DocumentState] = Field(default_factory=list)
    ambiguity_reason: str | None = None


class ChangedField(BaseModel):
    field: str
    before: Any = None
    after: Any = None


class SourceDiff(BaseModel):
    contract_version: str = MONITORING_CONTRACT_VERSION
    outcome: Literal["UNCHANGED", "CHANGED", "NEEDS_REVIEW"]
    changes: list[ChangedField] = Field(default_factory=list)
    reason: str | None = None
    previous_fingerprint: str
    current_fingerprint: str


class AlertEvent(BaseModel):
    contract_version: str = MONITORING_CONTRACT_VERSION
    source: str
    external_id: str
    source_url: str | None = None
    event_key: str
    outcome: Literal["CHANGED", "NEEDS_REVIEW"]
    changes: list[ChangedField] = Field(default_factory=list)
    reason: str | None = None

class WatchResponse(WatchTarget):
    id: str
    model_config = {"from_attributes": True}


class FeedEventResponse(AlertEvent):
    id: str
    created_at: datetime
