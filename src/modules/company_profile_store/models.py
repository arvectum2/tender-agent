from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class CompanyProfileFactVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "company_profile_fact_versions"

    customer_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("customer_profiles.customer_id"), nullable=False
    )
    fact_key: Mapped[str] = mapped_column(String(128), nullable=False)
    fact_group: Mapped[str] = mapped_column(String(32), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    value_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "fact_key",
            "version_no",
            name="uq_company_profile_fact_version",
        ),
        Index("ix_company_profile_fact_customer_key", "customer_id", "fact_key"),
        Index("ix_company_profile_fact_expiry", "customer_id", "expires_at"),
    )


class CompanyDocument(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "company_documents"

    customer_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("customer_profiles.customer_id"), nullable=False
    )
    document_key: Mapped[str] = mapped_column(String(128), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_ref: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("document_artifacts.artifact_ref"),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "customer_id", "document_key", name="uq_company_document_customer_key"
        ),
        Index("ix_company_document_customer_type", "customer_id", "document_type"),
    )


class CompanyDocumentVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "company_document_versions"

    company_document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("company_documents.id"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    document_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "company_document_id",
            "version_no",
            name="uq_company_document_version",
        ),
        UniqueConstraint(
            "company_document_id",
            "artifact_version_no",
            name="uq_company_document_artifact_version",
        ),
        Index(
            "ix_company_document_version_document", "company_document_id", "version_no"
        ),
        Index("ix_company_document_version_expiry", "expires_at"),
    )


def _immutable(*_args, **_kwargs) -> None:
    raise ValueError(
        "Company profile/document history is immutable; append a new version instead"
    )


for _model in (CompanyProfileFactVersion, CompanyDocument, CompanyDocumentVersion):
    event.listen(_model, "before_update", _immutable)
    event.listen(_model, "before_delete", _immutable)
