from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class DailyTenderRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "daily_tender_runs"

    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    profile_id: Mapped[str] = mapped_column(String(128), nullable=False)
    profile_version: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    counts_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    digest_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_daily_tender_runs_profile_created", "profile_id", "created_at"),
        Index("ix_daily_tender_runs_status", "status"),
    )


class DailyTenderRunItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "daily_tender_run_items"

    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("daily_tender_runs.run_id"), nullable=False
    )
    registry_number: Mapped[str] = mapped_column(String(32), nullable=False)
    law: Mapped[str] = mapped_column(String(16), nullable=False, default="44fz")
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    customer_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    nmck_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    query_hits_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    stage: Mapped[str] = mapped_column(String(64), nullable=False, default="DISCOVER")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DISCOVERED")
    screening_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    screening_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    screening_reasons_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    changed_since_previous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deal_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("deals.deal_id"), nullable=True)
    analysis_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_report_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_recommendation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    agent_confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    agent_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    strongest_reasons_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    blockers_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    unknowns_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    synthesis_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("run_id", "registry_number", name="uq_daily_tender_run_item_registry"),
        Index("ix_daily_tender_run_items_run_status", "run_id", "status"),
        Index("ix_daily_tender_run_items_registry", "registry_number"),
        Index("ix_daily_tender_run_items_deal", "deal_id"),
    )
