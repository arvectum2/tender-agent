from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class ProcurementWatch(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "procurement_watches"

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    saved_search: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_procurement_watches_source_external"),)


class ProcurementWatchSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "procurement_watch_snapshots"

    watch_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_watches.id"), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("watch_id", "fingerprint", name="uq_procurement_watch_snapshot_fingerprint"),
        Index("ix_procurement_watch_snapshots_watch_created", "watch_id", "created_at"),
    )


class ProcurementWatchEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "procurement_watch_events"

    watch_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_watches.id"), nullable=False)
    event_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (Index("ix_procurement_watch_events_watch_created", "watch_id", "created_at"),)
