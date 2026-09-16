from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class IntegrationOutboxEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "integration_outbox_events"
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(256), nullable=False)
    envelope: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_integration_outbox_event_key"),
        Index("ix_integration_outbox_tenant_created", "tenant_id", "created_at"),
        Index("ix_integration_outbox_type_created", "event_type", "created_at"),
    )
