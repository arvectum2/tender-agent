from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from src.shared.types.common import APIModel


class DemoStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    PARTIAL = "partial"
    NEEDS_REVIEW = "needs_review"
    WARNING = "warning"
    BLOCKED = "blocked"


class DemoRecommendationCode(StrEnum):
    PARTICIPATE = "participate"
    PARTICIPATE_CONDITIONALLY = "participate_conditionally"
    DO_NOT_PARTICIPATE = "do_not_participate"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class DemoDocument(APIModel):
    name: str
    role: str
    pages: int = Field(ge=1)


class DemoDetailSection(APIModel):
    title: str
    kind: str = Field(pattern="^(bullets|table)$")
    columns: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class DemoTenderCard(APIModel):
    run_id: str
    prepared_at: datetime
    title: str
    procedure_type: str
    customer: str
    category: str
    procurement_code: str
    submission_deadline: datetime
    analysis_status: str
    document_count: int = Field(ge=0)
    requirement_count: int = Field(ge=0)
    question_count: int = Field(ge=0)
    final_recommendation: DemoRecommendationCode
    final_recommendation_label: str
    documents: list[DemoDocument]


class DemoStep(APIModel):
    key: str
    order: int = Field(ge=0)
    title: str
    short_title: str
    status: DemoStepStatus
    description: str
    agent_action: str
    result_summary: str
    findings: list[str]
    human_review: list[str]
    trace: str
    result_sections: list[DemoDetailSection] = Field(default_factory=list)


class DemoFinalRecommendation(APIModel):
    recommendation: DemoRecommendationCode
    label: str
    rationale: list[str]
    key_requirements: list[str]
    open_questions: list[str]
    risks: list[str]
    economics: list[str]
    manual_checks: list[str]
    trace: str


class DemoReportAction(APIModel):
    label: str
    href: str
    enabled: bool = True
    note: str | None = None


class DemoSafetyNotice(APIModel):
    demo_mode: bool = True
    human_in_the_loop: bool = True
    synthetic_data: bool = True
    restrictions: list[str]
    message: str


class TenderOperatorDemoRunResponse(APIModel):
    demo_mode: bool = True
    tenant_name: str = "Arvectum"
    title: str = "Tender Operator Agent Demo"
    title_ru: str = "Тендерный агент: демонстрация работы"
    subtitle: str
    tender: DemoTenderCard
    steps: list[DemoStep]
    final_recommendation: DemoFinalRecommendation
    trace_summary: list[str]
    safety: DemoSafetyNotice
    report_actions: list[DemoReportAction]


class TenderOperatorDemoStepsResponse(APIModel):
    run_id: str
    steps: list[DemoStep]


class TenderOperatorDemoReportResponse(APIModel):
    run_id: str
    report_title: str
    generated_at: datetime
    recommendation: DemoRecommendationCode
    recommendation_label: str
    executive_summary: list[str]
    manual_checks: list[str]
    sections: list[DemoDetailSection]
    report_markdown: str
    decision_core: dict[str, Any] | None = None
    commercial_core: dict[str, Any] | None = None


class TenderOperatorUploadedRunStatus(StrEnum):
    UPLOADED = "uploaded"
    DOCS_REQUIRED = "docs_required"
    READY_TO_ANALYZE = "ready_to_analyze"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class TenderOperatorRunEvent(APIModel):
    created_at: datetime
    event_type: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None
    message_ru: str | None = None
    step: str = "Система"
    severity: str = Field(default="info", pattern="^(info|warning|error)$")
    metadata: dict[str, Any] = Field(default_factory=dict)


class TenderOperatorRunEventFeedItem(APIModel):
    timestamp: datetime
    event_type: str
    message_ru: str
    step: str
    severity: str = Field(default="info", pattern="^(info|warning|error)$")


class ProcurementSourceDescriptor(APIModel):
    code: str
    label: str
    enabled: bool = True
    read_only: bool = True
    note: str | None = None


class ProcurementSearchResult(APIModel):
    procurement_id: str
    source: str
    title: str
    procurement_number: str | None = None
    customer_name: str
    category: str
    publication_date: str | None = None
    deadline: str | None = None
    initial_price: float | None = None
    currency: str | None = None
    region: str | None = None
    source_url: str
    attachments_status: str
    attachments_count: int = Field(ge=0, default=0)
    available_attachments_count: int = Field(ge=0, default=0)
    summary: str | None = None
    attachment_names: list[str] = Field(default_factory=list)
    source_note: str | None = None


class ProcurementSearchResponse(APIModel):
    query: str
    source: str
    results: list[ProcurementSearchResult]
    sources: list[ProcurementSourceDescriptor]
    warnings: list[str] = Field(default_factory=list)


class ProcurementRunCreateRequest(APIModel):
    procurement_id: str
    source: str
    query: str | None = None
    download_attachments: bool = True


class EisDocsArchiveRunRequest(APIModel):
    reestr_number: str
    law: str = "44fz"
    subsystem_type: str = "PRIZ"
    method: str = "getDocsByReestrNumber"
    download_archive: bool = True
    analyze_after_download: bool = False


class PublicSearchUrlResponse(APIModel):
    source: str
    law: str
    query: str
    eis_search_url: str
    note: str


class ProcurementAttachmentManifestItem(APIModel):
    name: str
    stored_name: str | None = None
    extension: str
    status: str
    note: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    document_kind: str | None = None
    content_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    error: str | None = None
    provenance: dict[str, Any] | None = None


class ProcurementRunResponse(APIModel):
    run_id: str
    status: TenderOperatorUploadedRunStatus
    created_at: datetime
    file_count: int = Field(ge=0, default=0)
    run_url: str | None = None
    report_url: str | None = None
    downloaded_files_count: int = Field(ge=0, default=0)
    manual_upload_required: bool = True
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    attachments_status: str
    procurement: ProcurementSearchResult
    attachments: list[ProcurementAttachmentManifestItem] = Field(default_factory=list)
    archive_url_present: bool = False
    archive_downloaded: bool = False
    archive_download_status: str | None = None
    archive_download_attempts: int = Field(default=0, ge=0)
    documents_extracted_count: int = Field(default=0, ge=0)
    analysis_status: str | None = None
    soap_method: str | None = None
    ref_id: str | None = None
    archive_source_host: str | None = None
    archive_source_path: str | None = None


class SearchResultHandoffRequest(APIModel):
    source: str = "public_44fz"
    law: str | None = None
    reestr_number: str
    source_url: str | None = None
    title: str | None = None
    customer_name: str | None = None
    initial_price: float | None = None
    publication_date: str | None = None
    deadline: str | None = None
    currency: str | None = None
    status: str | None = None
    procedure_type: str | None = None
    download_archive: bool = True
    analyze_after_download: bool = True


class SearchResultHandoffResponse(APIModel):
    run_id: str
    status: str
    archive_url_present: bool = False
    archive_downloaded: bool = False
    documents_extracted_count: int = Field(default=0, ge=0)
    analysis_status: str | None = None
    run_url: str | None = None
    report_url: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ProcurementRunDetailsResponse(APIModel):
    run_id: str
    procurement: ProcurementSearchResult
    attachments_status: str
    attachments: list[ProcurementAttachmentManifestItem] = Field(default_factory=list)
    events: list[TenderOperatorRunEvent] = Field(default_factory=list)


class TenderOperatorUploadedFile(APIModel):
    file_id: str
    original_name: str
    display_name: str
    stored_name: str
    role_hint: str | None = None
    extension: str
    size_bytes: int = Field(ge=0)
    content_type: str
    source: str = "upload"
    extracted_text_available: bool = False
    warnings: list[str] = Field(default_factory=list)


class TenderOperatorUploadedRunSummary(APIModel):
    run_id: str
    created_at: datetime
    mode: str
    tender_title: str
    tender_category: str
    customer_name: str
    status: TenderOperatorUploadedRunStatus
    analysis_mode: str
    file_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    limitations: list[str] = Field(default_factory=list)
    procurement_source: str | None = None
    procurement_id: str | None = None
    attachments_status: str | None = None


class TenderOperatorUploadedRunResponse(APIModel):
    run_id: str
    created_at: datetime
    mode: str
    tender_title: str
    tender_category: str
    customer_name: str
    notes: str | None = None
    status: TenderOperatorUploadedRunStatus
    analysis_mode: str
    files: list[TenderOperatorUploadedFile]
    limitations: list[str]
    warnings: list[str]
    human_in_the_loop: bool = True
    external_actions: bool = False
    no_platform_submission: bool = True
    no_email_sending: bool = True
    no_digital_signature: bool = True
    procurement_source: str | None = None
    procurement_id: str | None = None
    procurement_url: str | None = None
    procurement_query: str | None = None
    procurement_notice_number: str | None = None
    procurement_law: str | None = None
    token_owner: str | None = None
    soap_method: str | None = None
    eis_ref_id: str | None = None
    archive_url_present: bool = False
    archive_downloaded: bool = False
    archive_download_status: str | None = None
    archive_download_attempts: int = Field(default=0, ge=0)
    archive_source_host: str | None = None
    archive_source_path: str | None = None
    documents_extracted_count: int = Field(default=0, ge=0)
    downloaded_files_count: int = Field(default=0, ge=0)
    manual_upload_required: bool = False
    attachments_status: str | None = None
    steps: list[DemoStep] = Field(default_factory=list)
    final_recommendation: DemoFinalRecommendation | None = None
    quote_comparison: QuoteComparison | None = None
    economics_summary: EconomicsSummary | None = None
    report_html_url: str | None = None
    report_download_url: str | None = None
    uploaded_files_note: str | None = None
    events: list[TenderOperatorRunEvent] = Field(default_factory=list)
    document_relevance: dict | None = None


class TenderOperatorUploadedRunListResponse(APIModel):
    runs: list[TenderOperatorUploadedRunSummary]


class TenderOperatorUploadedRunCreateResponse(APIModel):
    run_id: str
    status: TenderOperatorUploadedRunStatus
    created_at: datetime
    file_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class TenderOperatorUploadedRunAnalyzeResponse(APIModel):
    run_id: str
    status: TenderOperatorUploadedRunStatus
    analysis_mode: str
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    steps: list[DemoStep]
    final_recommendation: DemoFinalRecommendation


class TenderOperatorUploadedRunStepsResponse(APIModel):
    run_id: str
    status: TenderOperatorUploadedRunStatus
    steps: list[DemoStep]


class ExtractionWarning(APIModel):
    code: str
    message: str
    level: str = "warning"


class ManualCheck(APIModel):
    code: str
    message: str
    severity: str = "needs_review"


class QuoteOffer(APIModel):
    supplier_name: str
    offered_name: str
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    total_price: float | None = None
    delivery: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    warnings: list[str] = Field(default_factory=list)


class QuoteItem(APIModel):
    item_number: str | None = None
    row_number: int | None = None
    normalized_name: str
    requested_quantity: float | None = None
    unit: str | None = None
    manufacturer: str | None = None
    currency: str | None = None
    source_file: str
    source_sheet: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    warnings: list[str] = Field(default_factory=list)
    offers: list[QuoteOffer] = Field(default_factory=list)
    best_price_supplier: str | None = None
    price_spread_percent: float | None = None
    needs_review: bool = False


class SupplierQuote(APIModel):
    supplier_id: str
    supplier_name: str
    source_file: str
    source_sheet: str | None = None
    document_type: str
    total_amount: float | None = None
    currency: str | None = None
    items_count: int = Field(ge=0)
    delivery_summary: str | None = None
    completeness_score: float = Field(ge=0.0, le=1.0, default=0.0)
    price_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    warnings: list[str] = Field(default_factory=list)
    items: list[QuoteItem] = Field(default_factory=list)


class QuoteComparison(APIModel):
    status: str
    analysis_mode: str
    supplier_quotes_found: int = Field(ge=0)
    items_extracted: int = Field(ge=0)
    suppliers: list[SupplierQuote] = Field(default_factory=list)
    items: list[QuoteItem] = Field(default_factory=list)
    comparison_summary: dict[str, Any] = Field(default_factory=dict)
    manual_checks: list[ManualCheck] = Field(default_factory=list)
    warnings: list[ExtractionWarning] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class EconomicsSummary(APIModel):
    status: str
    analysis_mode: str
    currency: str | None = None
    supplier_cost_min: float | None = None
    supplier_cost_selected: float | None = None
    expected_revenue: float | None = None
    preliminary_bid_price: float | None = None
    gross_margin_amount: float | None = None
    gross_margin_percent: float | None = None
    logistics_reserve: float | None = None
    risk_reserve: float | None = None
    payment_delay_days: int | None = None
    cash_gap_estimate: float | None = None
    economics_status: str
    selected_supplier_name: str | None = None
    assumptions: dict[str, Any] = Field(default_factory=dict)
    manual_checks: list[ManualCheck] = Field(default_factory=list)
    warnings: list[ExtractionWarning] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
