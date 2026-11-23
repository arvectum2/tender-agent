from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class ProcurementTender(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "procurement_tenders"

    source: Mapped[str] = mapped_column(String(64), nullable=False, default="eis")
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    registry_number: Mapped[str | None] = mapped_column(String(256), nullable=True)
    purchase_number: Mapped[str | None] = mapped_column(String(256), nullable=True)
    law_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    customer_inn: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_kpp: Mapped[str | None] = mapped_column(String(32), nullable=True)
    region: Mapped[str | None] = mapped_column(String(256), nullable=True)
    platform_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    platform_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    eis_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    nmck_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auction_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    documents: Mapped[list[ProcurementTenderDocument]] = relationship(back_populates="tender", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("source", "external_id"),
        Index("ix_procurement_tenders_registry_number", "registry_number"),
        Index("ix_procurement_tenders_customer_inn", "customer_inn"),
        Index("ix_procurement_tenders_publication_date", "publication_date"),
        Index("ix_procurement_tenders_application_deadline", "application_deadline"),
        Index("ix_procurement_tenders_content_hash", "content_hash"),
    )


class ProcurementCustomer(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "procurement_customers"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    inn: Mapped[str | None] = mapped_column(String(32), nullable=True)
    kpp: Mapped[str | None] = mapped_column(String(32), nullable=True)
    region: Mapped[str | None] = mapped_column(String(256), nullable=True)
    normalized_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    tenders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_last_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("inn", "kpp"),
        Index("ix_procurement_customers_normalized_name", "normalized_name"),
    )


class ProcurementTenderDocument(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "procurement_tender_documents"

    tender_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_tenders.id"), nullable=False, index=True)
    source_document_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    file_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(256), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    document_identity_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    document_identity_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    download_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    text_extraction_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    extracted_text_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    tender: Mapped[ProcurementTender] = relationship(back_populates="documents")
    chunks: Mapped[list[ProcurementDocumentChunk]] = relationship(back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tender_id", "sha256"),
        Index("ix_procurement_tender_documents_download_status", "download_status"),
        Index("ix_procurement_tender_documents_text_extraction_status", "text_extraction_status"),
        Index("ix_procurement_tender_documents_identity_hash", "tender_id", "document_identity_hash"),
    )


class ProcurementDocumentChunk(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "procurement_document_chunks"

    tender_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_tenders.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_tender_documents.id"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_file_name: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_text_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    document: Mapped[ProcurementTenderDocument] = relationship(back_populates="chunks")
    embeddings: Mapped[list[ProcurementDocumentEmbedding]] = relationship(back_populates="chunk", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        UniqueConstraint("document_id", "text_hash"),
        Index("ix_procurement_document_chunks_text_hash", "text_hash"),
    )


class TenderAsyncIndexReceipt(UUIDPrimaryKeyMixin, Base):
    """Durable DP job receipts (metadata only; never source content or API secrets)."""

    __tablename__ = "tender_async_index_receipts"

    tender_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_tenders.id"), nullable=False)
    collection_id: Mapped[str] = mapped_column(String(128), nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    indexed_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("collection_id", "chunk_id", name="uq_tender_async_receipt_source"),
        UniqueConstraint("collection_id", "job_id", name="uq_tender_async_receipt_job"),
        Index("ix_tender_async_receipt_tender_collection", "tender_id", "collection_id"),
    )


class ProcurementDocumentEmbedding(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "procurement_document_embeddings"

    chunk_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_document_chunks.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(256), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    embedding_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    chunk: Mapped[ProcurementDocumentChunk] = relationship(back_populates="embeddings")

    __table_args__ = (
        UniqueConstraint("chunk_id", "provider", "model"),
        Index("ix_procurement_document_embeddings_vector_id", "vector_id"),
    )


class ProcurementTenderSearchQuery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "procurement_tender_search_queries"

    tender_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_tenders.id"), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    results_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tender_id", "provider", "query"),
        Index("ix_procurement_tender_search_queries_provider", "provider"),
        Index("ix_procurement_tender_search_queries_query_type", "query_type"),
    )


class ProcurementWebSearchResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "procurement_web_search_results"

    tender_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_tenders.id"), nullable=False, index=True)
    query_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_tender_search_queries.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    display_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("query_id", "url_hash"),
        Index("ix_procurement_web_search_results_normalized_url", "normalized_url"),
        Index("ix_procurement_web_search_results_url_hash", "url_hash"),
    )


class ProcurementWebPage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "procurement_web_pages"

    tender_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("procurement_tenders.id"), nullable=True, index=True)
    search_result_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("procurement_web_search_results.id"), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fetcher: Mapped[str] = mapped_column(String(32), nullable=False, default="requests")
    fetch_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(256), nullable=True)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("url_hash"),
        Index("ix_procurement_web_pages_fetch_status", "fetch_status"),
        Index("ix_procurement_web_pages_content_type", "content_type"),
    )


class TenderAnalysisRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "tender_analysis_runs"

    registry_number: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    used_llm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    retrieval_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retrieval_model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    sections_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_markdown_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    errors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Nullable only for R7 history. Every R8 customer workflow run has all three.
    customer_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("customer_profiles.customer_id"), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("pilot_projects.id"), nullable=True)
    procurement_case_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("procurement_cases.id"), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    artifact_key: Mapped[str | None] = mapped_column(String(96), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_tender_analysis_runs_registry_number", "registry_number"),
        Index("ix_tender_analysis_runs_status", "status"),
        Index("ix_tender_analysis_runs_created_at", "created_at"),
        Index("ix_tender_analysis_runs_customer_project_case", "customer_id", "project_id", "procurement_case_id"),
        UniqueConstraint("procurement_case_id", "idempotency_key", name="uq_r8_run_case_idempotency"),
    )


class TenderAnalysisJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "tender_analysis_jobs"

    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    registry_number: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_step: Mapped[str | None] = mapped_column(String(64), nullable=True)
    steps_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    errors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    request_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_tender_analysis_jobs_registry_number", "registry_number"),
        Index("ix_tender_analysis_jobs_job_type", "job_type"),
        Index("ix_tender_analysis_jobs_status", "status"),
        Index("ix_tender_analysis_jobs_created_at", "created_at"),
    )


class ProcurementRawArtifact(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "procurement_raw_artifacts"

    tender_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("procurement_tenders.id"), nullable=True, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    local_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(256), nullable=True)
    raw_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("sha256"),
        Index("ix_procurement_raw_artifacts_artifact_type", "artifact_type"),
    )
