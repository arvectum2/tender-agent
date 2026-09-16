from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from src.shared.types.common import APIModel


class ProcurementSourceStatus(APIModel):
    source: str
    label: str
    enabled: bool
    configured: bool
    read_only: bool = True
    reason: str | None = None
    safe_diagnostics: dict[str, Any] = Field(default_factory=dict)


class ProcurementSearchRequest(APIModel):
    source: str = "demo_local"
    query: str = ""
    law: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    customer_name: str | None = None
    customer_inn: str | None = None
    region: str | None = None
    price_from: float | None = None
    price_to: float | None = None
    max_results: int = Field(default=10, ge=1, le=50)


class ProcurementSearchOutcome(StrEnum):
    SUCCESS_WITH_RESULTS = "success_with_results"
    SUCCESS_EMPTY = "success_empty"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_NOT_CONFIGURED = "source_not_configured"
    SOURCE_ERROR = "source_error"
    UNSUPPORTED_SEARCH_MODE = "unsupported_search_mode"
    VALIDATION_ERROR = "validation_error"


class ProcurementAttachment(APIModel):
    attachment_id: str
    name: str
    url: str | None = None
    content_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    extension: str | None = None
    document_kind: str | None = None
    can_download: bool = False
    requires_manual_upload: bool = False
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] | None = None


class ProcurementSearchResult(APIModel):
    procurement_id: str
    notice_number: str | None = None
    registry_number: str | None = None
    title: str
    customer_name: str
    customer_inn: str | None = None
    law: str | None = None
    source: str
    source_url: str
    publication_date: str | None = None
    deadline: str | None = None
    initial_price: float | None = None
    currency: str | None = None
    status: str | None = None
    attachments_count: int = Field(default=0, ge=0)
    attachments_status: str = "unknown"
    can_download_attachments: bool = False
    requires_manual_upload: bool = True
    warnings: list[str] = Field(default_factory=list)


class PublicProcurementSearchResponse(APIModel):
    status: str
    outcome: ProcurementSearchOutcome
    query: str = ""
    source: str = "public_eis_html_44fz"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1)
    returned_count: int = Field(default=0, ge=0)
    total_count: int | None = Field(default=None, ge=0)
    total_count_source: str | None = None
    total_count_exact_for_displayed_filters: bool = False
    raw_returned_count: int | None = Field(default=None, ge=0)
    local_filtered_count: int = Field(default=0, ge=0)
    local_post_filter_applied: bool = False
    eis_pages_fetched: int = Field(default=1, ge=0)
    has_more: bool = False
    next_page: int | None = Field(default=None, ge=1)
    next_cursor: str | None = None
    requested_limit: int | None = Field(default=None, ge=1)
    sort: str | None = None
    cards: list[dict[str, Any]] = Field(default_factory=list)
    eis_search_url: str | None = None
    error: str | None = None
    parser_status: str | None = None
    message: str
    warnings: list[str] = Field(default_factory=list)


class ProcurementDetails(APIModel):
    procurement: ProcurementSearchResult
    attachments: list[ProcurementAttachment] = Field(default_factory=list)
    raw_source_summary: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ProcurementIntakeResult(APIModel):
    run_id: str
    status: str
    run_url: str
    report_url: str | None = None
    downloaded_files_count: int = Field(default=0, ge=0)
    manual_upload_required: bool = True
    warnings: list[str] = Field(default_factory=list)


class DocsArchiveResult(APIModel):
    request_id: str
    ref_id: str | None = None
    archive_url: str | None = None
    archive_urls: list[str] = Field(default_factory=list)
    archive_name: str | None = None
    archive_size: int | None = Field(default=None, ge=0)
    status: str
    warnings: list[str] = Field(default_factory=list)
    raw_summary: str | None = None
    safe_diagnostic: dict[str, Any] = Field(default_factory=dict)


class DownloadedAttachment(APIModel):
    file_name: str
    stored_name: str
    size_bytes: int = Field(ge=0)
    content_type: str | None = None
    source_url_host: str | None = None
    source_url_path: str | None = None


class ProcurementEvent(APIModel):
    event_type: str
    timestamp: datetime
    message_ru: str
    step: str
    severity: str = Field(default="info", pattern="^(info|warning|error)$")
    metadata: dict[str, Any] = Field(default_factory=dict)
