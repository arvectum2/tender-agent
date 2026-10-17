"""Candidate observations for a future LLM live inside the existing Tender Agent DB."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.db.base import Base, utcnow


class ProcurementLearningObservation(Base):
    __tablename__ = "procurement_learning_observations"

    observation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    procurement_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    participation: Mapped[str] = mapped_column(String(32), nullable=False)
    review_state: Mapped[str] = mapped_column(String(40), nullable=False)
    training_status: Mapped[str] = mapped_column(String(40), nullable=False, default="candidate_unreviewed")
    candidate_split: Mapped[str] = mapped_column(String(64), nullable=False)
    visibility_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint("training_status = 'candidate_unreviewed'", name="ck_learning_observation_not_gold"),
        CheckConstraint(
            "visibility_scope = 'owner_internal' OR "
            "(visibility_scope = 'tenant' AND customer_id IS NOT NULL)",
            name="ck_learning_observation_scoped",
        ),
        Index("ix_learning_observations_procurement", "procurement_ref"),
        Index("ix_learning_observations_customer", "customer_id", "created_at"),
        Index("ix_learning_observations_kind", "event_kind"),
    )
