from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class CaseJournalEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "case_journal_entries"

    customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    procurement_case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("procurement_cases.id"), nullable=False
    )
    entry_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    decision_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    supersedes_entry_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("case_journal_entries.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        Index(
            "ix_case_journal_scope_created",
            "customer_id",
            "project_id",
            "procurement_case_id",
            "created_at",
        ),
        Index("ix_case_journal_case_entry_type", "procurement_case_id", "entry_type"),
    )


class CaseJournalMention(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "case_journal_mentions"

    journal_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("case_journal_entries.id"), nullable=False
    )
    mention_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    notification_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="INTERNAL_UNREAD"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        Index("ix_case_journal_mentions_entry", "journal_entry_id"),
        Index("ix_case_journal_mentions_ref", "mention_ref"),
    )


class CaseJournalEvidenceLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "case_journal_evidence_links"

    journal_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("case_journal_entries.id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        Index("ix_case_journal_evidence_entry", "journal_entry_id"),
        Index("ix_case_journal_evidence_source", "source_type", "source_ref"),
    )


def _immutable(*_args, **_kwargs) -> None:
    raise ValueError(
        "Case collaboration history is immutable; append a new entry instead"
    )


for _model in (CaseJournalEntry, CaseJournalMention, CaseJournalEvidenceLink):
    event.listen(_model, "before_update", _immutable)
    event.listen(_model, "before_delete", _immutable)
