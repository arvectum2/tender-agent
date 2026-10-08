from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class ApplicationDraftGeneration(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "application_draft_generations"

    deal_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("deals.deal_id"), nullable=False
    )
    template_artifact_ref: Mapped[str] = mapped_column(
        String(64), ForeignKey("document_artifacts.artifact_ref"), nullable=False
    )
    output_artifact_ref: Mapped[str] = mapped_column(
        String(64), ForeignKey("document_artifacts.artifact_ref"), nullable=False
    )
    document_role: Mapped[str] = mapped_column(String(32), nullable=False)
    output_format: Mapped[str] = mapped_column(String(16), nullable=False)
    lineage_key: Mapped[str] = mapped_column(String(192), nullable=False)
    template_version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    generation_version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    template_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    output_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    output_file_name: Mapped[str] = mapped_column(Text, nullable=False)
    output_storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    review_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT_REVIEW_ONLY"
    )
    signature_performed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    submission_performed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    external_delivery_performed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "deal_id",
            "lineage_key",
            "generation_version_no",
            name="uq_application_draft_lineage_version",
        ),
        Index("ix_application_draft_deal_role", "deal_id", "document_role"),
        Index("ix_application_draft_output_artifact", "output_artifact_ref"),
    )


class ApplicationDraftFieldProvenance(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "application_draft_field_provenance"

    generation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("application_draft_generations.id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    target_locator: Mapped[str] = mapped_column(Text, nullable=False)
    original_value_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    generated_value_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "generation_id",
            "target_locator",
            name="uq_application_draft_generation_target",
        ),
        Index("ix_application_draft_field_generation", "generation_id"),
        Index("ix_application_draft_field_source", "source_type"),
    )
