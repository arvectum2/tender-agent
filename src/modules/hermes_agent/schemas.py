from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HermesLineItem(BaseModel):
    position_no: str = ""
    name: str = ""
    unit: str = ""
    quantity: str = ""
    characteristics: list[str] = []
    standards: list[str] = []
    equivalent_allowed: bool = True
    source_document_id: str = ""
    source_document: str = ""
    source_quote: str = ""
    source_locator: dict[str, Any] = Field(default_factory=dict)
    quantity_status: str | None = None
    unit_status: str | None = None
    missing_reason: str | None = None
    tender_id: str = ""
    run_id: str = ""
    confidence: float = 0.0


class HermesSummary(BaseModel):
    subject: str = ""
    customer: str = ""
    nmck: str = ""
    delivery_address: str = ""
    delivery_term: str = ""


class HermesTechnicalRequirement(BaseModel):
    requirement: str = ""
    source_document: str = ""
    source_quote: str = ""
    confidence: float = 0.0


class HermesCertificationRequirement(BaseModel):
    requirement: str = ""
    source_document: str = ""
    source_quote: str = ""
    confidence: float = 0.0


class HermesContractRisk(BaseModel):
    risk: str = ""
    severity: str = "info"
    source_document: str = ""
    source_quote: str = ""
    confidence: float = 0.0


class HermesMissingData(BaseModel):
    field: str = ""
    reason: str = ""
    suggested_source: str = ""


class HermesQualityCheck(BaseModel):
    check_name: str = ""
    status: str = "passed"
    message: str = ""


class HermesFinalRecommendation(BaseModel):
    status: str = "ready"
    reason: str = ""


class HermesAnalysisResponse(BaseModel):
    tender_id: str = ""
    registry_number: str = ""
    run_id: str = ""
    document_roles: list[str] = []
    summary: HermesSummary = HermesSummary()
    line_items: list[HermesLineItem] = []
    technical_requirements: list[HermesTechnicalRequirement] = []
    certification_requirements: list[HermesCertificationRequirement] = []
    contract_risks: list[HermesContractRisk] = []
    missing_data: list[HermesMissingData] = []
    quality_checks: list[HermesQualityCheck] = []
    final_recommendation: HermesFinalRecommendation = HermesFinalRecommendation()


class HermesContextRequest(BaseModel):
    tender_id: str
    include_chunks: bool = False
    include_tables: bool = True


class HermesAnalysisRequest(BaseModel):
    tender_id: str
    force: bool = False


class HermesMemoryCreateRequest(BaseModel):
    memory_type: str
    scope: str = "general"
    category: str = "general"
    payload_json: dict = {}
    source_tender_id: str | None = None


class HermesMemorySearchRequest(BaseModel):
    memory_type: str | None = None
    scope: str | None = None
    category: str | None = None
    source_tender_id: str | None = None
    customer_id: str | None = None
    project_id: str | None = None
    procurement_case_id: str | None = None
    limit: int = 20


class HermesFeedbackCreateRequest(BaseModel):
    tender_id: str
    analysis_id: str | None = None
    customer_id: str | None = None
    project_id: str | None = None
    procurement_case_id: str | None = None
    field_path: str
    feedback_type: str = "correction"
    user_comment: str | None = None
    corrected_value_json: dict | None = None


class HermesEvalCaseCreateRequest(BaseModel):
    tender_id: str
    fixture_name: str
    expected_json: dict | None = None
    must_include_json: dict | None = None
    must_not_include_json: dict | None = None


class HermesEvalCaseResponse(BaseModel):
    id: str
    tender_id: str
    fixture_name: str
    must_include_json: dict | None
    must_not_include_json: dict | None
    created_at: datetime


class HermesDocumentContext(BaseModel):
    id: str
    file_name: str
    role: str = ""
    text: str = ""
    tables: list[dict] = []
    extracted_text_chars: int = 0


class HermesRelevantMemory(BaseModel):
    id: str
    memory_type: str = ""
    scope: str = ""
    category: str = ""
    payload_json: dict = {}


class HermesRuntimeContext(BaseModel):
    tender_id: str
    tender: dict[str, Any] = {}
    documents: list[HermesDocumentContext] = []
    document_roles: list[str] = []
    relevant_memory: list[HermesRelevantMemory] = []


class HermesRuntimeAnalysisRequest(BaseModel):
    tender_id: str
    force: bool = False


class NormalizedLineItem(BaseModel):
    raw_name: str = ""
    normalized_name: str = ""
    type_mark: str | None = None
    cores_count: int | None = None
    cross_section_mm2: float | None = None
    voltage: float | None = None
    conductor_material: str | None = None
    insulation_material: str | None = None
    standard: str | None = None
    equivalent_allowed: bool | None = None


class NmckLine(BaseModel):
    name: str = ""
    quantity: str = ""
    unit: str = ""
    price: str = ""
    total_amount: str = ""


class NmckMappingItem(BaseModel):
    line_item_index: int = 0
    line_item_name: str = ""
    nmck_index: int | None = None
    nmck_name: str | None = None
    nmck_price: str | None = None
    nmck_total_amount: str | None = None
    match_score: float = 0.0
    match_method: str = "none"


class NmckMappingResult(BaseModel):
    total_nmck_lines: int = 0
    mapped_count: int = 0
    unmapped_count: int = 0
    mapping_status: str = "no_nmck_data"
    items: list[NmckMappingItem] = []


class SupplierRequiredDocument(BaseModel):
    name: str = ""
    reason: str = ""
    source_document: str = ""
    source_quote: str = ""
    required: bool = True
    confidence: float = 0.0


class SupplierMissingData(BaseModel):
    field: str = ""
    reason: str = ""
    needed_for: str = ""
    priority: str = "medium"


class SupplierRisk(BaseModel):
    risk_type: str = "technical"
    severity: str = "medium"
    title: str = ""
    description: str = ""
    mitigation: str = ""
    source_document: str = ""
    source_quote: str = ""
    confidence: float = 0.0


class QuestionToCustomer(BaseModel):
    question: str = ""
    reason: str = ""
    related_line_item: str = ""
    source_document: str = ""
    source_quote: str = ""
    priority: str = "medium"


class RfqRequirement(BaseModel):
    line_item_ref: str = ""
    normalized_name: str = ""
    quantity: str = ""
    unit: str = ""
    required_characteristics: list[str] = []
    certificates_required: list[str] = []
    delivery_terms: str = ""
    price_needed: bool = True


class SupplierReadinessMemo(BaseModel):
    tender_id: str = ""
    bid_decision: str = "needs_review"
    decision_reason: str = ""
    supplier_readiness_score: int = 0
    required_documents: list[SupplierRequiredDocument] = []
    missing_supplier_data: list[SupplierMissingData] = []
    technical_risks: list[SupplierRisk] = []
    commercial_risks: list[SupplierRisk] = []
    contract_risks: list[SupplierRisk] = []
    blocking_risks: list[SupplierRisk] = []
    questions_to_customer: list[QuestionToCustomer] = []
    rfq_requirements: list[RfqRequirement] = []
    next_actions: list[str] = []
    source_coverage_pct: float = 0.0
    created_at: str = ""


class HermesRuntimeAnalysisResult(HermesAnalysisResponse):
    applied_memory_count: int = 0
    improvement_attempted: bool = False
    improvement_succeeded: bool = False
    evidence_coverage_pct: float = 0.0
    documents_used_count: int = 0
    documents_total_count: int = 0
    analysis_duration_ms: float = 0.0
    procurement_category: str = "general_goods"
    category_label: str = ""
    normalized_line_items: list[NormalizedLineItem] = []
    nmck_mapping: NmckMappingResult = NmckMappingResult()
    supplier_readiness_memo: SupplierReadinessMemo | None = None
