from __future__ import annotations

import html  # noqa: F401 - retain legacy attribute for consumers
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from fastapi import HTTPException
from fastapi.responses import FileResponse

from src.modules.procurement_analysis.document_roles import detect_document_role
from src.modules.supplier_search.internet_supplier_search import SupplierSearchOutcome
from src.modules.tender_operator_agent_demo.contract_term_facts import (
    extract_contract_term_facts,
)
from src.modules.tender_operator_agent_demo.document_source_projection import (
    project_document_source,
)
from src.modules.tender_operator_agent_demo.event_log import (
    append_tender_demo_event,
    load_tender_demo_events,
)
from src.modules.tender_operator_agent_demo.goods_source_facts import (
    build_complete_goods_positions,
    build_goods_requirements_from_source_facts,
    detect_procurement_richness,
    extract_goods_source_facts,
    semantic_procurement_role,
)
from src.modules.tender_operator_agent_demo.operator_analysis_text_helpers import (
    project_is_goods_supply_table_present,
    project_rewrite_compliance_highlight,
    project_rewrite_delivery_model_item,
)
from src.modules.tender_operator_agent_demo.operator_analysis_trace import (
    build_operator_analysis_trace,
)
from src.modules.tender_operator_agent_demo.operator_archive_intake import (
    read_operator_zip_documents,
)
from src.modules.tender_operator_agent_demo.operator_document_collection import (
    collect_operator_documents,
    collect_operator_quote_paths,
    collect_operator_role_text,
    collect_operator_spreadsheet_sources,
)
from src.modules.tender_operator_agent_demo.operator_document_extraction import (
    extract_operator_document,
)
from src.modules.tender_operator_agent_demo.operator_document_rows import (
    build_software_work_rows,
    extract_meaningful_snippets,
)
from src.modules.tender_operator_agent_demo.operator_economics_persistence import (
    _coerce_economics_summary_payload as _coerce_economics_summary_payload,  # noqa: PLC0414 - old serialization facade
)
from src.modules.tender_operator_agent_demo.operator_economics_persistence import (
    _coerce_quote_comparison_payload as _coerce_quote_comparison_payload,  # noqa: PLC0414 - old serialization facade
)
from src.modules.tender_operator_agent_demo.operator_economics_persistence import (
    _maybe_float as _maybe_float,  # noqa: PLC0414 - old serialization facade
)
from src.modules.tender_operator_agent_demo.operator_economics_persistence import (
    _serialize_economics_summary as _serialize_economics_summary,  # noqa: PLC0414 - old serialization facade
)
from src.modules.tender_operator_agent_demo.operator_economics_persistence import (
    _serialize_quote_comparison as _serialize_quote_comparison,  # noqa: PLC0414 - old serialization facade
)
from src.modules.tender_operator_agent_demo.operator_goods_economics import (
    build_goods_economics_payload,
)
from src.modules.tender_operator_agent_demo.operator_goods_preliminary import (
    project_build_goods_preliminary_analysis,
)
from src.modules.tender_operator_agent_demo.operator_goods_reconciliation import (
    project_collect_unmerged_source_items,
    project_merge_supply_items,
)
from src.modules.tender_operator_agent_demo.operator_goods_text_fields import (
    split_trailing_classification,
    summarize_supply_characteristics,
)
from src.modules.tender_operator_agent_demo.operator_llm_outcome import (
    _classify_controlled_llm_result as _classify_controlled_llm_result,  # noqa: PLC0414 - legacy facade
)
from src.modules.tender_operator_agent_demo.operator_llm_report_projection import (
    candidate_requirement_rows,
    candidate_rfq_sections,
    candidate_risks,
    candidate_supplier_questions,
)
from src.modules.tender_operator_agent_demo.operator_non_goods_economics import (
    build_non_goods_economics_payload,
)
from src.modules.tender_operator_agent_demo.operator_notice_fields import (
    extract_notice_delivery_deadline,
    extract_notice_price,
)
from src.modules.tender_operator_agent_demo.operator_notice_text_helpers import (
    project_collect_matches,
    project_extract_inline_goods_field,
    project_extract_notice_service_deadline,
)
from src.modules.tender_operator_agent_demo.operator_output_orchestrator import (
    project_build_output_payloads,
)
from src.modules.tender_operator_agent_demo.operator_preliminary_orchestrator import (
    project_build_preliminary_procurement_analysis,
)
from src.modules.tender_operator_agent_demo.operator_quote_report import (
    build_quote_comparison_report,
)
from src.modules.tender_operator_agent_demo.operator_recommendation import (
    build_provisional_operator_recommendation,
)
from src.modules.tender_operator_agent_demo.operator_report_inventory import (
    build_downloaded_documents_inventory,
    document_type_label,
)
from src.modules.tender_operator_agent_demo.operator_report_renderers import (
    project_render_procurement_blocked_report_html,
    project_render_product_report_html,
)
from src.modules.tender_operator_agent_demo.operator_requirement_rows import (
    extract_requirement_rows,
    normalize_requirement_title,
)
from src.modules.tender_operator_agent_demo.operator_requirements_context import (
    build_operator_requirements_context,
)
from src.modules.tender_operator_agent_demo.operator_rfq_document_projections import (
    build_document_grounded_questions,
    build_document_grounded_requirements,
    build_goods_rfq_payload,
    project_document_grounded_risks,
)
from src.modules.tender_operator_agent_demo.operator_risk_report import (
    build_document_grounded_rfq_sections,
    build_document_grounded_risks,  # noqa: F401 - preserve legacy module re-export
    build_operator_risk_payload,
)
from src.modules.tender_operator_agent_demo.operator_scope_classifier import (
    _SCOPE_SIGNALS as _SCOPE_SIGNALS,  # noqa: PLC0414 - legacy facade
)
from src.modules.tender_operator_agent_demo.operator_scope_classifier import (
    _classify_procurement_scope as _classify_procurement_scope,  # noqa: PLC0414 - legacy facade
)
from src.modules.tender_operator_agent_demo.operator_scope_classifier import (
    _is_generic_procurement_scope_boilerplate as _is_generic_procurement_scope_boilerplate,  # noqa: PLC0414 - legacy facade
)
from src.modules.tender_operator_agent_demo.operator_scope_classifier import (
    _scope_signal_evidence as _scope_signal_evidence,  # noqa: PLC0414 - legacy facade
)
from src.modules.tender_operator_agent_demo.operator_services_analysis import (
    project_build_services_preliminary_analysis,
)
from src.modules.tender_operator_agent_demo.operator_software_preliminary import (
    build_software_preliminary_analysis,
)
from src.modules.tender_operator_agent_demo.operator_spec_rows import (
    extract_legacy_goods_spec_rows,
)
from src.modules.tender_operator_agent_demo.operator_stored_file_paths import (
    checked_original_input_path,
)
from src.modules.tender_operator_agent_demo.operator_submission_deadline import (
    submission_deadline_from_metadata,
)
from src.modules.tender_operator_agent_demo.operator_supplier_questions import (
    normalize_supplier_questions,
)
from src.modules.tender_operator_agent_demo.operator_supply_rows import (
    service_item_analysis_rows,
    supply_item_to_row,
)
from src.modules.tender_operator_agent_demo.operator_supply_source_parsers import (
    extract_service_items_from_nmck_text,
    extract_supply_items_from_notification_xml,
    extract_supply_items_from_spec_text,
)
from src.modules.tender_operator_agent_demo.operator_supply_xlsx import (
    extract_supply_items_from_xlsx_text,
)
from src.modules.tender_operator_agent_demo.operator_tender_summary import (
    build_operator_tender_summary,
)
from src.modules.tender_operator_agent_demo.operator_training_location_action import (
    build_training_location_action,
)
from src.modules.tender_operator_agent_demo.operator_training_source_facts import (
    extract_training_candidate_facts,
)
from src.modules.tender_operator_agent_demo.operator_upload_descriptors import (
    _build_file_descriptor as _build_file_descriptor,  # noqa: PLC0414 - legacy import facade
)
from src.modules.tender_operator_agent_demo.operator_upload_descriptors import (
    build_demo_file_descriptor as build_demo_file_descriptor,  # noqa: PLC0414 - legacy import facade
)
from src.modules.tender_operator_agent_demo.operator_upload_economics_input import (
    _sanitize_delay_days as _sanitize_delay_days,  # noqa: PLC0414 - compatibility facade
)
from src.modules.tender_operator_agent_demo.operator_upload_economics_input import (
    _sanitize_percent as _sanitize_percent,  # noqa: PLC0414 - compatibility facade
)
from src.modules.tender_operator_agent_demo.operator_upload_filenames import (
    ALLOWED_EXTENSIONS,
    sanitize_demo_filename,
)
from src.modules.tender_operator_agent_demo.operator_upload_preflight import (
    validate_operator_upload_batch,
)
from src.modules.tender_operator_agent_demo.procurement_discovery import (
    get_supplier_profile,
)
from src.modules.tender_operator_agent_demo.quote_normalizer import (
    SpreadsheetSource,
    build_economics_summary,
    build_quote_comparison,
)
from src.modules.tender_operator_agent_demo.relevance_scoring import (
    score_procurement_document_text,
)
from src.modules.tender_operator_agent_demo.schemas import (
    DemoFinalRecommendation,
    DemoRecommendationCode,
    DemoStep,
    DemoStepStatus,
    TenderOperatorDemoReportResponse,
    TenderOperatorRunEvent,
    TenderOperatorUploadedFile,
    TenderOperatorUploadedRunAnalyzeResponse,
    TenderOperatorUploadedRunCreateResponse,
    TenderOperatorUploadedRunListResponse,
    TenderOperatorUploadedRunResponse,
    TenderOperatorUploadedRunStatus,
    TenderOperatorUploadedRunStepsResponse,
    TenderOperatorUploadedRunSummary,
)
from src.shared.config.settings import get_settings
from src.shared.document_processing import (
    ProcessedDocument,
    process_document_bytes,
)
from src.tender_research.rag.presets import tender_processing_collection_id

MAX_FILE_COUNT = 16
MAX_FILE_SIZE_BYTES = 12 * 1024 * 1024
MAX_TOTAL_UPLOAD_BYTES = 40 * 1024 * 1024
MAX_ZIP_ENTRY_COUNT = 32
MAX_ZIP_TOTAL_BYTES = 24 * 1024 * 1024
METADATA_FILE = "metadata.json"
EVENTS_FILE = "events.jsonl"
DEFAULT_TARGET_MARGIN_PERCENT = 15.0
DEFAULT_LOGISTICS_RESERVE_PERCENT = 3.0
DEFAULT_RISK_RESERVE_PERCENT = 5.0
DEFAULT_PAYMENT_DELAY_DAYS = 45

TEXT_TRANSLATIONS = {
    "Compliance with specified technical standards required": "Требуется соответствие указанным техническим стандартам.",
    "Equipment/goods must match stated specifications": "Оборудование и товары должны соответствовать заявленной спецификации.",
    "Acceptance testing per contract terms": "Нужно пройти приёмочные испытания по условиям договора.",
    "Warranty and post-delivery support required": "Требуются гарантия и поддержка после поставки.",
    "Company registration certificate": "Свидетельство о регистрации компании.",
    "Tax clearance certificate": "Справка об отсутствии налоговой задолженности.",
    "Technical proposal with specifications": "Техническое предложение со спецификацией.",
    "Financial guarantee or contract security": "Финансовое обеспечение или обеспечение исполнения договора.",
    "Declaration of conformity": "Декларация о соответствии.",
    "Can you supply the exact item matching the specification? If not, what analog do you propose?": "Можете ли вы поставить точную позицию по спецификации? Если нет, какой аналог предлагаете?",
    "What is your price per unit with VAT and without VAT?": "Укажите цену за единицу с НДС и без НДС.",
    "What is the delivery cost to the specified location?": "Укажите стоимость доставки до указанного объекта.",
    "What is the delivery time from order confirmation?": "Какой срок поставки после подтверждения заказа?",
    "Is the item in stock or made to order? If made to order, what is the manufacturing lead time?": "Позиция в наличии или производится под заказ? Если под заказ, какой срок изготовления?",
    "Do you have the required certificates and declarations of conformity?": "Есть ли необходимые сертификаты и декларации соответствия?",
    "What warranty do you provide?": "Какой гарантийный срок вы предоставляете?",
    "Do you offer an analog that meets the specification? If so, provide details.": "Предлагаете ли аналог, соответствующий спецификации? Если да, укажите детали.",
    "What are your payment terms? Do you require prepayment?": "Какие условия оплаты? Требуется ли предоплата?",
    "How long is your offer valid?": "Какой срок действия вашего предложения?",
    "Is installation/assembly included? If not, what are the additional costs?": "Входит ли монтаж или сборка? Если нет, какие дополнительные затраты?",
    "Is packaging, delivery, and unloading included? If not, what are the additional costs?": "Включены ли упаковка, доставка и разгрузка? Если нет, какие дополнительные затраты?",
    "Penalties for delay": "Штрафы за просрочку.",
    "Post-payment after acceptance": "Оплата после приёмки.",
    "Unilateral termination right": "Право одностороннего расторжения.",
    "Contract security requirement": "Требование обеспечения исполнения договора.",
    "Short delivery timeline": "Сжатый срок поставки.",
    "Required license/SRO/experience": "Обязательная лицензия, СРО или подтверждённый опыт.",
    "Manageable. Include in project planning.": "Риск управляемый. Нужно заложить его в план исполнения.",
    "Standard for public procurement. Requires working capital.": "Типично для закупок. Требует оборотного капитала.",
    "Standard clause. Manageable with proper project management.": "Стандартное условие. Управляется при дисциплине исполнения.",
    "Binds significant working capital. Reduces available margin.": "Замораживает заметный объём оборотных средств и снижает доступную маржу.",
    "Requires supplier with stock or short manufacturing lead time.": "Нужен поставщик со складским остатком или коротким циклом производства.",
    "If operator/supplier cannot meet these, participation is impossible.": "Если оператор или поставщик не соответствуют этому требованию, участвовать нельзя.",
    "Ensure realistic delivery timeline. Include buffer.": "Подтвердить реалистичный срок поставки и заложить буфер.",
    "Factor into cash flow planning. Consider contract security reduction.": "Учесть это в cash-flow и отдельно оценить возможность снижения обеспечения.",
    "Track milestones diligently. Communicate proactively.": "Жёстко контролировать вехи исполнения и заранее эскалировать отклонения.",
    "Include cost of security (bank guarantee fee) in pricing. Negotiate reduction if possible.": "Включить стоимость обеспечения в цену и, если возможно, согласовать снижение.",
    "Verify supplier availability before bidding. Consider partial delivery.": "До участия подтвердить наличие у поставщика и рассмотреть частичную поставку.",
    "Verify requirements early. Check if equivalents are accepted.": "Сразу проверить требования и отдельно уточнить, принимаются ли эквиваленты.",
}


def _translate_user_text(value: str) -> str:
    return TEXT_TRANSLATIONS.get(value, value)


from src.modules.procurement_analysis.frozen_types import AnalyzedDocument


@dataclass
class SupplyItem:
    item_no: str | None
    name: str
    quantity: str | None
    unit: str | None
    characteristics: list[str]
    gost: list[str]
    equivalent_allowed: bool | None
    source_document: str
    source_kind: str
    confidence: str
    raw_fragment: str
    unit_price: str | None = None
    total_price: str | None = None
    source_documents: list[str] = field(default_factory=list)
    item_type: str = "goods"
    quantity_status: str = "specified"
    pricing_basis: str = "unknown"
    source_row_number: int | None = None
    evidence_id: str | None = None
    unit_original: str | None = None
    record_type: str = "line_item"
    unit_code: str | None = None
    ktru: str | None = None
    okpd2: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)
    name_source_type: str = "unresolved"
    name_source_path: str | None = None
    quantity_source_path: str | None = None
    unit_source_path: str | None = None
    source_record_id: str | None = None
    extraction_strategy: str = "unknown"
    evidence_ids: list[str] = field(default_factory=list)
    official_name: str | None = None
    display_name: str | None = None


def get_demo_runs_root() -> Path:
    configured = os.environ.get("AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[3] / "company_agent_runs" / "tender_operator_demo"


def _ensure_runs_root() -> Path:
    root = get_demo_runs_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_demo_run_dir(run_id: str) -> Path:
    return _ensure_runs_root() / run_id


def get_demo_run_procurement_dir(run_id: str) -> Path:
    return get_demo_run_dir(run_id) / "procurement"


def get_demo_run_input_dir(run_id: str) -> Path:
    return get_demo_run_dir(run_id) / "input"


def get_demo_run_normalized_dir(run_id: str) -> Path:
    return get_demo_run_dir(run_id) / "normalized"


def get_demo_run_output_dir(run_id: str) -> Path:
    return get_demo_run_dir(run_id) / "output"




def _metadata_path(run_id: str) -> Path:
    return get_demo_run_dir(run_id) / METADATA_FILE


def _input_dir(run_id: str) -> Path:
    return get_demo_run_input_dir(run_id)


def _normalized_dir(run_id: str) -> Path:
    return get_demo_run_normalized_dir(run_id)


def _output_dir(run_id: str) -> Path:
    return get_demo_run_output_dir(run_id)


def _safe_datetime() -> str:
    return datetime.now(UTC).isoformat()


def make_demo_run_id() -> str:
    return f"toa-run-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{token_hex(3)}"




def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))






def ensure_demo_run_structure(run_id: str, *, exist_ok: bool) -> dict[str, Path]:
    run_dir = get_demo_run_dir(run_id)
    input_dir = get_demo_run_input_dir(run_id)
    normalized_dir = get_demo_run_normalized_dir(run_id)
    output_dir = get_demo_run_output_dir(run_id)
    procurement_dir = get_demo_run_procurement_dir(run_id)
    input_dir.mkdir(parents=True, exist_ok=exist_ok)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    procurement_dir.mkdir(parents=True, exist_ok=True)
    return {
        "run_dir": run_dir,
        "input_dir": input_dir,
        "normalized_dir": normalized_dir,
        "output_dir": output_dir,
        "procurement_dir": procurement_dir,
    }


def load_demo_run_metadata(run_id: str) -> dict[str, Any]:
    path = _metadata_path(run_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' was not found")
    return _read_json(path)


def save_demo_run_metadata(run_id: str, metadata: dict[str, Any]) -> None:
    _write_json(_metadata_path(run_id), metadata)


def append_demo_run_event(run_id: str, event_type: str, message: str, details: dict[str, Any] | None = None) -> None:
    append_tender_demo_event(run_id, event_type, message, details or {})


def load_demo_run_events(run_id: str) -> list[TenderOperatorRunEvent]:
    return [TenderOperatorRunEvent.model_validate(item) for item in load_tender_demo_events(run_id)]






def create_uploaded_demo_run(
    *,
    tender_title: str,
    tender_category: str,
    customer_name: str,
    notes: str | None,
    target_margin_percent: float | None,
    logistics_reserve_percent: float | None,
    risk_reserve_percent: float | None,
    payment_delay_days: int | None,
    uploads: list[tuple[str, str, bytes]],
) -> TenderOperatorUploadedRunCreateResponse:
    """Compatibility facade: retain runtime patches and public signature."""
    from src.modules.tender_operator_agent_demo.operator_create_run import (
        create_uploaded_demo_run as _create_run,
    )

    return _create_run(
        tender_title=tender_title,
        tender_category=tender_category,
        customer_name=customer_name,
        notes=notes,
        target_margin_percent=target_margin_percent,
        logistics_reserve_percent=logistics_reserve_percent,
        risk_reserve_percent=risk_reserve_percent,
        payment_delay_days=payment_delay_days,
        uploads=uploads,
        HTTPException=HTTPException,
        validate_operator_upload_batch=validate_operator_upload_batch,
        MAX_FILE_COUNT=MAX_FILE_COUNT,
        MAX_FILE_SIZE_BYTES=MAX_FILE_SIZE_BYTES,
        MAX_TOTAL_UPLOAD_BYTES=MAX_TOTAL_UPLOAD_BYTES,
        sanitize_demo_filename=sanitize_demo_filename,
        _sanitize_percent=_sanitize_percent,
        DEFAULT_TARGET_MARGIN_PERCENT=DEFAULT_TARGET_MARGIN_PERCENT,
        DEFAULT_LOGISTICS_RESERVE_PERCENT=DEFAULT_LOGISTICS_RESERVE_PERCENT,
        DEFAULT_RISK_RESERVE_PERCENT=DEFAULT_RISK_RESERVE_PERCENT,
        _sanitize_delay_days=_sanitize_delay_days,
        DEFAULT_PAYMENT_DELAY_DAYS=DEFAULT_PAYMENT_DELAY_DAYS,
        make_demo_run_id=make_demo_run_id,
        ensure_demo_run_structure=ensure_demo_run_structure,
        Path=Path,
        build_demo_file_descriptor=build_demo_file_descriptor,
        _derive_role_hint=_derive_role_hint,
        _safe_datetime=_safe_datetime,
        TenderOperatorUploadedRunStatus=TenderOperatorUploadedRunStatus,
        save_demo_run_metadata=save_demo_run_metadata,
        append_demo_run_event=append_demo_run_event,
        TenderOperatorUploadedRunCreateResponse=TenderOperatorUploadedRunCreateResponse,
        datetime=datetime,
    )


def append_files_to_demo_run(
    *,
    run_id: str,
    uploads: list[tuple[str, str, bytes]],
) -> TenderOperatorUploadedRunCreateResponse:
    """Compatibility facade: use current patched dependencies at call time."""
    from src.modules.tender_operator_agent_demo.operator_append_files import (
        append_files_to_demo_run as _append_files,
    )

    return _append_files(
        run_id=run_id,
        uploads=uploads,
        _load_metadata=_load_metadata,
        validate_operator_upload_batch=validate_operator_upload_batch,
        MAX_FILE_COUNT=MAX_FILE_COUNT,
        MAX_FILE_SIZE_BYTES=MAX_FILE_SIZE_BYTES,
        MAX_TOTAL_UPLOAD_BYTES=MAX_TOTAL_UPLOAD_BYTES,
        sanitize_demo_filename=sanitize_demo_filename,
        _input_dir=_input_dir,
        Path=Path,
        build_demo_file_descriptor=build_demo_file_descriptor,
        _derive_role_hint=_derive_role_hint,
        append_demo_run_event=append_demo_run_event,
        TenderOperatorUploadedRunStatus=TenderOperatorUploadedRunStatus,
        save_demo_run_metadata=save_demo_run_metadata,
        TenderOperatorUploadedRunCreateResponse=TenderOperatorUploadedRunCreateResponse,
        datetime=datetime,
    )


def list_uploaded_demo_runs() -> TenderOperatorUploadedRunListResponse:
    root = _ensure_runs_root()
    runs: list[TenderOperatorUploadedRunSummary] = []
    for path in sorted(root.iterdir(), reverse=True):
        metadata_path = path / METADATA_FILE
        if not metadata_path.is_file():
            continue
        metadata = _read_json(metadata_path)
        runs.append(
            TenderOperatorUploadedRunSummary(
                run_id=metadata["run_id"],
                created_at=datetime.fromisoformat(metadata["created_at"]),
                mode=metadata["mode"],
                tender_title=metadata["tender_title"],
                tender_category=metadata["tender_category"],
                customer_name=metadata["customer_name"],
                status=TenderOperatorUploadedRunStatus(metadata["status"]),
                analysis_mode=metadata.get("analysis_mode", "not_started"),
                file_count=len(metadata.get("files", [])),
                warning_count=len(metadata.get("warnings", [])),
                limitations=metadata.get("limitations", []),
                procurement_source=metadata.get("procurement_source"),
                procurement_id=metadata.get("procurement_id"),
                attachments_status=metadata.get("attachments_status"),
            )
        )
    runs.sort(key=lambda item: item.created_at, reverse=True)
    return TenderOperatorUploadedRunListResponse(runs=runs[:12])


def _load_metadata(run_id: str) -> dict[str, Any]:
    return load_demo_run_metadata(run_id)


def _save_metadata(run_id: str, metadata: dict[str, Any]) -> None:
    save_demo_run_metadata(run_id, metadata)




def _detect_role(name: str) -> str:
    """Compatibility facade for the storage-neutral frozen-pipeline policy."""
    return detect_document_role(name)


def _derive_role_hint(filename: str) -> str | None:
    lowered = filename.lower()
    if lowered.startswith("technical_spec_"):
        return "technical_spec"
    if lowered.startswith("contract_draft_"):
        return "contract_draft"
    if lowered.startswith("notice_"):
        return "notice"
    if lowered.startswith("tkp_"):
        return "tkp"
    detected = _detect_role(filename)
    return detected if detected != "supporting" else None


def _extract_document_text_with_provenance(
    file_name: str,
    content: bytes,
) -> tuple[str | None, list[str], str, ProcessedDocument | None]:
    """Compatibility shim over the generic Data Platform processor."""
    return extract_operator_document(
        file_name=file_name,
        content=content,
        collection_id=tender_processing_collection_id("upload"),
        processor=process_document_bytes,
    )


def _extract_document_text(
    file_name: str,
    content: bytes,
) -> tuple[str | None, list[str], str]:
    """Preserve original legacy 3-value result for ZIP and external callers."""
    text, warnings, status, _processed = _extract_document_text_with_provenance(file_name, content)
    return text, warnings, status


def _extract_zip_documents(path: Path, parent_file_id: str) -> list[AnalyzedDocument]:
    """Compatibility shim over the isolated, bounded ZIP decoder."""
    return read_operator_zip_documents(
        path,
        parent_file_id,
        allowed_extensions=ALLOWED_EXTENSIONS,
        max_entries=MAX_ZIP_ENTRY_COUNT,
        max_total_bytes=MAX_ZIP_TOTAL_BYTES,
        extract_text=_extract_document_text,
        detect_role=_detect_role,
    )


def _collect_documents(run_id: str, metadata: dict[str, Any]) -> list[AnalyzedDocument]:
    """Preserve legacy extension points while delegating document assembly."""
    return collect_operator_documents(
        metadata=metadata,
        input_dir=_input_dir(run_id),
        normalized_dir=_normalized_dir(run_id),
        checked_path=checked_original_input_path,
        extract_archive=_extract_zip_documents,
        extract_with_provenance=_extract_document_text_with_provenance,
        project_source=project_document_source,
        detect_role=_detect_role,
    )


def _collect_role_text(documents: list[AnalyzedDocument], role: str) -> str:
    return collect_operator_role_text(documents, role)


def _collect_quote_paths(run_id: str, metadata: dict[str, Any]) -> list[Path]:
    return collect_operator_quote_paths(
        metadata=metadata,
        input_dir=_input_dir(run_id),
        checked_path=checked_original_input_path,
        detect_role=_detect_role,
    )


def _collect_spreadsheet_sources(documents: list[AnalyzedDocument]) -> list[SpreadsheetSource]:
    return collect_operator_spreadsheet_sources(documents)




def _try_run_llm_workflow(
    run_id: str,
    notice_text: str | None,
    technical_spec_text: str | None,
    contract_draft_text: str | None,
    quote_paths: list[Path],
    provider_mode: str = "llm",
) -> dict[str, Any] | None:
    """Legacy compatibility shim; no other source of controlled workflow logic."""
    from src.modules.tender_operator_agent_demo.operator_llm_workflow import (
        run_controlled_operator_llm,
    )

    return run_controlled_operator_llm(
        run_id=run_id,
        notice_text=notice_text,
        technical_spec_text=technical_spec_text,
        contract_draft_text=contract_draft_text,
        quote_paths=quote_paths,
        provider_mode=provider_mode,
        emit_event=append_demo_run_event,
        settings_getter=get_settings,
    )




def _runtime_ai_provenance() -> dict[str, Any]:
    """Record observed local runtime facts, never credentials or prompts."""
    settings = get_settings()
    started = time.perf_counter()
    endpoint = settings.local_llm_base_url.rstrip("/") + "/models"
    healthcheck = "unreachable"
    model = settings.llm_model or settings.local_llm_model
    try:
        with urlopen(endpoint, timeout=2) as response:  # local loopback only
            payload = json.loads(response.read().decode("utf-8"))
        models = payload.get("data", [])
        if models:
            model = str(models[0].get("id") or model)
        healthcheck = "ok"
    except Exception:
        healthcheck = "unreachable"
    return {
        "analysis_engine": "deterministic",
        "llm_invoked": False,
        "llm_provider": settings.llm_provider,
        "llm_model": model,
        "llm_endpoint_host": urlparse(settings.local_llm_base_url).hostname,
        "hermes_enabled": settings.hermes_enabled,
        "hermes_healthcheck": "not_configured" if not settings.hermes_enabled else "not_checked",
        "prompt_version": "semantic-matcher-v1",
        "llm_calls_count": 0,
        "llm_latency_ms": round((time.perf_counter() - started) * 1000),
        "fallback_reason": "local_llm_endpoint_unreachable" if healthcheck != "ok" else "local_llm_not_used_by_deterministic_extraction",
        "local_llm_healthcheck": healthcheck,
    }


def _run_supplier_internet_search(
    tender_title: str,
    notice_text: str | None = None,
    technical_spec_text: str | None = None,
) -> SupplierSearchOutcome:
    from src.modules.supplier_search.internet_supplier_search import search_suppliers
    from src.modules.supplier_search.yandex_search_client import YandexSearchClient

    settings = get_settings()
    api_key = settings.yandex_search_api_key
    folder_id = settings.yandex_search_folder_id
    if not api_key or not folder_id:
        return SupplierSearchOutcome(error="Yandex Search API не настроен. Добавьте AI_CORP_YANDEX_SEARCH_API_KEY и AI_CORP_YANDEX_SEARCH_FOLDER_ID.")
    try:
        client = YandexSearchClient(api_key=api_key, folder_id=folder_id, timeout=30)
        return search_suppliers(
            client=client,
            tender_title=tender_title,
            notice_text=notice_text,
            technical_spec_text=technical_spec_text,
            max_results=10,
        )
    except Exception:
        return SupplierSearchOutcome(error="Не удалось выполнить поиск поставщиков через Yandex Search API.")


def _infer_procurement_kind(*texts: str | None) -> str:
    """Compatibility facade for existing intake/report callers."""
    from src.modules.tender_operator_agent_demo.procurement_kind_classifier import (
        infer_procurement_kind,
    )

    return infer_procurement_kind(*texts)














def _normalize_requirement_title(title: str, procurement_kind: str) -> str | None:
    return normalize_requirement_title(title, procurement_kind, translate=_translate_user_text)


def _extract_requirement_rows(
    requirements: dict[str, Any], core_complete: bool, procurement_kind: str
) -> list[dict[str, str]]:
    return extract_requirement_rows(
        requirements, core_complete, procurement_kind, translate=_translate_user_text
    )


def _match_first(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            value = " ".join(group for group in match.groups() if group)
            value = re.sub(r"\s+", " ", value).strip(" .;,\n\t")
            if value:
                return value
    return None


def _collect_matches(text: str, patterns: tuple[str, ...], *, limit: int=6) -> list[str]:
    """Compatibility facade for product-owned text projector."""
    return project_collect_matches(text, patterns, limit=limit)


def _match_first_dotall(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            value = " ".join(group for group in match.groups() if group)
            value = re.sub(r"\s+", " ", value).strip(" .;,\n\t")
            if value:
                return value
    return None


def _normalize_analysis_sentence(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip(" .;,\n\t")
    if not cleaned:
        return None
    cleaned = cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned.upper()
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _dedupe_text_items(items: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = re.sub(r"\s+", " ", (item or "")).strip(" .").lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(item)
    return unique


def _shorten_payment_terms(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"(\d+)\s*\([^)]+\)\s*рабочих дней", r"\1 рабочих дней", value, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"после подписания Сторонами в единой информационной системе документа о приемке",
        "после подписания документа о приемке",
        cleaned,
        flags=re.IGNORECASE,
    )
    return _normalize_analysis_sentence(cleaned)


def _shorten_acceptance_terms(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"(\d+)\s*\([^)]+\)\s*рабочих дней", r"\1 рабочих дней", value, flags=re.IGNORECASE)
    cleaned = re.sub(
        r",?\s*следующих за днем поступления документа о приемке.*",
        " после поступления документа о приемке",
        cleaned,
        flags=re.IGNORECASE,
    )
    return _normalize_analysis_sentence(cleaned)


def _format_money_value(value: float | str | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        numeric = float(str(value).replace(" ", "").replace(",", "."))
    except ValueError:
        return str(value)
    return f"{numeric:,.2f}".replace(",", " ").replace(".", ",")


def _extract_notice_price(metadata: dict[str, Any], *texts: str) -> str | None:
    """Backward-compatible product-owned projection facade."""
    return extract_notice_price(metadata, *texts, _format_money_value=_format_money_value, _match_first_dotall=_match_first_dotall)


def _extract_notice_timeline(text: str, labels: tuple[str, ...], *, stop_markers: tuple[str, ...]) -> str | None:
    if not text:
        return None
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_pattern = "|".join(re.escape(marker) for marker in stop_markers)
    return _match_first_dotall(
        text,
        (
            rf"(?:{label_pattern})[^:\n<]*[:>\-]?\s*(.+?)(?=\s*(?:{stop_pattern})|\Z)",
        ),
    )


def _extract_notice_delivery_deadline(text: str) -> str | None:
    """Backward-compatible product-owned projection facade."""
    return extract_notice_delivery_deadline(text, _extract_notice_timeline=_extract_notice_timeline, _match_first_dotall=_match_first_dotall)


def _extract_notice_service_deadline(text: str) -> str | None:
    """Compatibility facade for product-owned text projector."""
    return project_extract_notice_service_deadline(text, _extract_notice_timeline=_extract_notice_timeline, _match_first_dotall=_match_first_dotall)


def _rewrite_compliance_highlight(value: str) -> str:
    """Compatibility facade for product-owned text projector."""
    return project_rewrite_compliance_highlight(value, _normalize_analysis_sentence=_normalize_analysis_sentence)


def _rewrite_delivery_model_item(value: str, procurement_kind: str) -> str:
    """Compatibility facade for product-owned text projector."""
    return project_rewrite_delivery_model_item(value, procurement_kind, _normalize_analysis_sentence=_normalize_analysis_sentence)


def _cleanup_tabular_value(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip(" .;,\n\t")
    cleaned = re.sub(r"\s+([,.:;])", r"\1", cleaned)
    cleaned = re.sub(r"([A-Za-zА-Яа-яЁё])\s+(\d)", r"\1 \2", cleaned)
    cleaned = re.sub(r"(\d)\s+([A-Za-zА-Яа-яЁё])", r"\1 \2", cleaned)
    return cleaned or None


def _extract_inline_goods_field(text: str, labels: tuple[str, ...], *, stop_markers: tuple[str, ...]) -> str | None:
    """Compatibility facade for product-owned text projector."""
    return project_extract_inline_goods_field(text, labels, stop_markers=stop_markers, _cleanup_tabular_value=_cleanup_tabular_value)


def _cleanup_delivery_address(value: str | None) -> str | None:
    cleaned = _cleanup_tabular_value(value)
    if not cleaned:
        return None
    address_match = re.search(r"по адресу:\s*(.+)$", cleaned, re.IGNORECASE)
    if address_match:
        cleaned = address_match.group(1)
    cleaned = re.sub(r"\s*Расходы по доставке.+$", "", cleaned, flags=re.IGNORECASE)
    return _cleanup_tabular_value(cleaned)


def _extract_goods_characteristics(section_text: str) -> str | None:
    normalized = _cleanup_tabular_value(section_text) or ""
    matches = re.findall(
        r"([А-ЯA-ZЁ][А-ЯA-Zа-яa-zЁё0-9 ,()/%-]{1,60})\s*:\s*([^:]{1,80}?)(?=\s+\d+\s+[А-ЯA-ZЁ]|$)",
        normalized,
    )
    items: list[str] = []
    for name, value in matches:
        left = _cleanup_tabular_value(name)
        right = _cleanup_tabular_value(value)
        if not left or not right:
            continue
        if left.lower().startswith(("параметры для", "инструкция по", "обоснование", "описание объекта закупки")):
            continue
        items.append(f"{left}: {right}")
        if len(items) >= 4:
            break
    return "; ".join(items) if items else None


_SUPPLY_UNIT_PATTERN = re.compile(
    r"^(шт|штука|м|м\.|м2|м3|кг|килограмм|г|грамм|л|миллилитр|компл(?:ект)?|комп|упак(?:овка)?|уп|пара|рул(?:он)?|набор|короб(?:ка)?|пачка|лист|ед\.?|усл\.?\s*ед\.?|пог\.?\s*м\.?)$",
    re.IGNORECASE,
)


def _is_goods_supply_table_present(text: str) -> bool:
    """Compatibility facade for product-owned text projector."""
    return project_is_goods_supply_table_present(text)


def _normalize_supply_name(value: str | None) -> str:
    cleaned = _cleanup_tabular_value(value) or ""
    cleaned = re.sub(r"\s+или\s+эквивалент\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    return cleaned.strip(" -") or "Позиция"


def _normalize_supply_name_key(value: str | None) -> str:
    cleaned = _normalize_supply_name(value).lower()
    cleaned = cleaned.replace("ё", "е")
    # OCR/DOCX line wrapping can split one word with a hyphen; it is not a
    # different procurement item from the structured XML spelling.
    cleaned = re.sub(r"(?<=[a-zа-я])[-‐‑–]\s*(?=[a-zа-я])", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bгост\b", "", cleaned)
    cleaned = re.sub(r"[^a-zа-я0-9]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _normalize_supply_unit(value: str | None) -> str | None:
    cleaned = (_cleanup_tabular_value(value) or "").lower().replace(" ", "")
    if cleaned in {"", "—", "данныхнедостаточнотребуетсяпроверка", "неуказано"} or "данныхнедостаточно" in cleaned:
        return None
    aliases = {
        "м.": "м",
        "пог.м.": "м",
        "пог.м": "м",
        "ед": "ед.",
        "ед.": "ед.",
        "комп": "компл",
        "штука": "шт",
        "упаковка": "упак",
        "миллилитр": "мл",
        "грамм": "г",
        "килограмм": "кг",
        "коробка": "короб",
    }
    return aliases.get(cleaned, cleaned) or None


def _is_line_item_name(value: str | None) -> bool:
    cleaned = _cleanup_tabular_value(value) or ""
    lowered = cleaned.lower()
    if lowered == "данных недостаточно — требуется проверка":
        return False
    if len(cleaned) < 3 or re.fullmatch(r"(?:гост|ту|ост|санпин)\s*[\d.\-–]+", lowered, re.IGNORECASE):
        return False
    disallowed = (
        "должен соответствовать", "требования к", "технические характеристики", "условия поставки",
        "гарантийн", "упаковк", "примечани", "описание объекта закупки", "наименование товара, услуги",
    )
    if any(marker in lowered for marker in disallowed):
        return False
    if re.fullmatch(r"(?:\d+(?:[.,]\d+)?\s*)?(?:в|кв|вт|квт|мм²|мм2|мм|см)", lowered):
        return False
    return bool(re.search(r"[a-zа-яё]", lowered, re.IGNORECASE))


def _is_ktru_or_okpd(value: str | None) -> bool:
    compact = (_cleanup_tabular_value(value) or "").replace(" ", "")
    return bool(re.fullmatch(r"\d{2,3}(?:\.\d{2,3}){1,4}(?:-\d+(?:-\d+)*)?", compact))


_TRAILING_CLASSIFICATION_RE = re.compile(
    r"^(?P<name>.+?)\s+(?P<label>КТРУ|ОКПД\s*2?)\s*[:-]?\s*"
    r"(?P<code>\d{2,3}(?:\.\d{2,3}){1,4}(?:-\d+(?:-\d+)*)?)\s*$",
    re.IGNORECASE,
)


def _split_trailing_classification(raw_name: str | None) -> tuple[str | None, str | None, str | None]:
    """Backward-compatible product-owned projection facade."""
    return split_trailing_classification(raw_name, _cleanup_tabular_value=_cleanup_tabular_value, _TRAILING_CLASSIFICATION_RE=_TRAILING_CLASSIFICATION_RE, _is_ktru_or_okpd=_is_ktru_or_okpd)


def _normalize_quantity_value(value: str | None) -> str | None:
    cleaned = _cleanup_tabular_value(value)
    if not cleaned:
        return None
    compact = cleaned.replace(" ", "")
    if not re.fullmatch(r"\d+(?:[.,]\d+)?", compact):
        return cleaned
    if "." in compact:
        compact = compact.rstrip("0").rstrip(".")
    if "," in compact:
        compact = compact.rstrip("0").rstrip(",")
    return compact


def _format_decimal_price(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def _parse_float(value: str | None) -> float | None:
    if not value:
        return None
    compact = value.replace(" ", "").replace(",", ".")
    try:
        return float(compact)
    except ValueError:
        return None


def _extract_gost_tokens(text: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for match in re.finditer(r"ГОСТ\s*[\d.]+(?:[-–]\d{2,4})?(?:-\d{4})?", text or "", re.IGNORECASE):
        raw = _cleanup_tabular_value(match.group(0))
        if not raw:
            continue
        token = raw.upper().replace("–", "-")
        if token in seen:
            continue
        seen.add(token)
        values.append(token)
    return values


def _summarize_supply_characteristics(values: list[str], *, limit: int = 6) -> list[str]:
    """Backward-compatible product-owned projection facade."""
    return summarize_supply_characteristics(values, limit=limit, _cleanup_tabular_value=_cleanup_tabular_value)


def _supply_item_to_row(item: SupplyItem) -> dict[str, Any]:
    """Backward-compatible facade."""
    return supply_item_to_row(item)


def _extract_supply_items_from_spec_text(text: str, source_document: str) -> list[SupplyItem]:
    """Legacy-compatible product parser facade."""
    return extract_supply_items_from_spec_text(
        text,
        source_document,
        supply_item_type=SupplyItem,
        supply_unit_pattern=_SUPPLY_UNIT_PATTERN,
        _is_goods_supply_table_present=_is_goods_supply_table_present,
        _cleanup_tabular_value=_cleanup_tabular_value,
        _normalize_supply_name=_normalize_supply_name,
        _is_line_item_name=_is_line_item_name,
        _normalize_supply_unit=_normalize_supply_unit,
        _normalize_quantity_value=_normalize_quantity_value,
        _summarize_supply_characteristics=_summarize_supply_characteristics,
        _extract_goods_characteristics=_extract_goods_characteristics,
        _extract_gost_tokens=_extract_gost_tokens,
    )



def _extract_supply_items_from_xlsx_text(text: str, source_document: str) -> list[SupplyItem]:
    """Backward-compatible facade: all source policy remains product-owned."""
    return extract_supply_items_from_xlsx_text(
        text,
        source_document,
        supply_item_type=SupplyItem,
        supply_unit_pattern=_SUPPLY_UNIT_PATTERN,
        _cleanup_tabular_value=_cleanup_tabular_value,
        _is_line_item_name=_is_line_item_name,
        _parse_float=_parse_float,
        _is_ktru_or_okpd=_is_ktru_or_okpd,
        _split_trailing_classification=_split_trailing_classification,
        _normalize_quantity_value=_normalize_quantity_value,
        _normalize_supply_name=_normalize_supply_name,
        _normalize_supply_unit=_normalize_supply_unit,
        _extract_gost_tokens=_extract_gost_tokens,
        _format_decimal_price=_format_decimal_price,
    )




def _extract_service_items_from_nmck_text(text: str, source_document: str) -> list[SupplyItem]:
    """Legacy-compatible product parser facade."""
    return extract_service_items_from_nmck_text(
        text,
        source_document,
        supply_item_type=SupplyItem,
        _cleanup_tabular_value=_cleanup_tabular_value,
        _parse_float=_parse_float,
        _normalize_supply_name=_normalize_supply_name,
        _normalize_supply_name_key=_normalize_supply_name_key,
        _normalize_supply_unit=_normalize_supply_unit,
        _format_decimal_price=_format_decimal_price,
    )



def _extract_supply_items_from_notification_xml(text: str, source_document: str) -> list[SupplyItem]:
    """Legacy-compatible product parser facade."""
    return extract_supply_items_from_notification_xml(
        text,
        source_document,
        supply_item_type=SupplyItem,
        _normalize_supply_name=_normalize_supply_name,
        _parse_float=_parse_float,
        _normalize_quantity_value=_normalize_quantity_value,
        _normalize_supply_unit=_normalize_supply_unit,
        _extract_gost_tokens=_extract_gost_tokens,
        _format_decimal_price=_format_decimal_price,
    )



def _service_subject_from_sources(metadata: dict[str, Any], notice_text: str, documents: list[AnalyzedDocument]) -> str:
    """Return a source-backed service subject, never a demo/report title."""
    subject = _match_first_dotall(
        notice_text,
        (r"<(?:\w+:)?purchaseObjectInfo>\s*([^<]+?)\s*</(?:\w+:)?purchaseObjectInfo>",),
    )
    if subject:
        return _cleanup_tabular_value(subject) or subject
    for document in documents:
        if document.role != "notice" or not document.text:
            continue
        subject = _match_first_dotall(
            document.text,
            (r"<(?:\w+:)?purchaseObjectInfo>\s*([^<]+?)\s*</(?:\w+:)?purchaseObjectInfo>",),
        )
        if subject:
            return _cleanup_tabular_value(subject) or subject
    return str(metadata.get("tender_title") or "Предмет закупки не извлечён")


def _service_okpd2_from_sources(notice_text: str, documents: list[AnalyzedDocument]) -> str | None:
    source_text = "\n".join([notice_text, *(doc.text or "" for doc in documents if doc.role == "notice")])
    return _match_first_dotall(
        source_text,
        (r"<(?:\w+:)?OKPDCode>\s*([\d.]+)\s*</(?:\w+:)?OKPDCode>",),
    )


def _is_vehicle_maintenance_services(subject: str, okpd2: str | None, service_items: list[SupplyItem]) -> bool:
    corpus = " ".join([subject, *(item.name for item in service_items)]).lower()
    return bool(
        (okpd2 or "").startswith("45.20")
        or ("автотранспорт" in corpus and any(token in corpus for token in ("диагност", "ремонт", "техническ")))
    )


def _service_item_analysis_rows(items: list[SupplyItem]) -> list[dict[str, Any]]:
    """Backward-compatible facade."""
    return service_item_analysis_rows(items)


def _build_services_preliminary_analysis(*, metadata: dict[str, Any], documents: list[AnalyzedDocument], notice_text: str, contract_draft_text: str) -> dict[str, Any]:
    """Legacy renderer and analysis compatibility facade."""
    return project_build_services_preliminary_analysis(metadata=metadata, documents=documents, notice_text=notice_text, contract_draft_text=contract_draft_text, _collect_supply_items=_collect_supply_items, _service_subject_from_sources=_service_subject_from_sources, _service_okpd2_from_sources=_service_okpd2_from_sources, _is_vehicle_maintenance_services=_is_vehicle_maintenance_services, _extract_notice_price=_extract_notice_price, _service_item_analysis_rows=_service_item_analysis_rows)


def _extract_legacy_goods_spec_rows(technical_spec_text: str) -> list[dict[str, str]]:
    """Backward-compatible facade."""
    return extract_legacy_goods_spec_rows(technical_spec_text, _cleanup_tabular_value=_cleanup_tabular_value, _extract_goods_characteristics=_extract_goods_characteristics, _extract_gost_tokens=_extract_gost_tokens, _normalize_quantity_value=_normalize_quantity_value)


def _merge_supply_items(items: list[SupplyItem]) -> list[SupplyItem]:
    """Compatibility facade preserving source-monolith runtime overrides."""
    return project_merge_supply_items(items, _is_line_item_name=_is_line_item_name, _normalize_supply_name_key=_normalize_supply_name_key, _normalize_supply_unit=_normalize_supply_unit, _summarize_supply_characteristics=_summarize_supply_characteristics)


def _collect_supply_items(documents: list[AnalyzedDocument]) -> list[SupplyItem]:
    return _merge_supply_items(_collect_unmerged_source_items(documents))


def _collect_unmerged_source_items(documents: list[AnalyzedDocument]) -> list[SupplyItem]:
    """Compatibility facade preserving source-monolith runtime overrides."""
    return project_collect_unmerged_source_items(documents, SupplyItem=SupplyItem, _extract_service_items_from_nmck_text=_extract_service_items_from_nmck_text, _extract_supply_items_from_notification_xml=_extract_supply_items_from_notification_xml, _extract_supply_items_from_spec_text=_extract_supply_items_from_spec_text, _extract_supply_items_from_xlsx_text=_extract_supply_items_from_xlsx_text, _is_line_item_name=_is_line_item_name, _normalize_supply_name=_normalize_supply_name, _normalize_supply_name_key=_normalize_supply_name_key, extract_goods_source_facts=extract_goods_source_facts)


def _extract_goods_spec_table(technical_spec_text: str) -> list[dict[str, str]]:
    rows = [_supply_item_to_row(item) for item in _extract_supply_items_from_spec_text(technical_spec_text, "Техническое задание")]
    return rows or _extract_legacy_goods_spec_rows(technical_spec_text)




def _build_supply_rows(documents: list[AnalyzedDocument]) -> list[dict[str, str]]:
    return [_supply_item_to_row(item) for item in _collect_supply_items(documents)]


def _document_source_label(doc: AnalyzedDocument) -> str:
    return doc.display_name


def _extract_meaningful_snippets(text: str, keywords: tuple[str, ...], *, max_snippets: int = 8) -> list[str]:
    """Backward-compatible facade."""
    return extract_meaningful_snippets(text, keywords, max_snippets=max_snippets)


def _build_software_work_rows(documents: list[AnalyzedDocument]) -> list[dict[str, str]]:
    """Backward-compatible facade."""
    return build_software_work_rows(documents, _cleanup_tabular_value=_cleanup_tabular_value, _document_source_label=_document_source_label, _extract_meaningful_snippets=_extract_meaningful_snippets)


def _collect_goods_supply_items_from_documents(documents: list[AnalyzedDocument]) -> list[SupplyItem]:
    return _collect_supply_items(documents)


def _build_goods_requirement_rows(documents: list[AnalyzedDocument]) -> list[dict[str, str]]:
    return build_goods_requirements_from_source_facts(extract_goods_source_facts(documents), limit=24)


def _build_goods_questions(documents: list[AnalyzedDocument]) -> list[str]:
    items = _collect_goods_supply_items_from_documents(documents)
    questions = [
        f"Подтверждаете поставку {item.name} в объёме {item.quantity or 'не указано'} {item.unit or ''}?".strip()
        for item in items[:6]
    ]
    questions.extend(
        [
            "Укажите производителя, марку, ГОСТ/ТУ и страну происхождения по каждой позиции.",
            "Подтвердите наличие сертификатов, деклараций и паспортов качества по поставляемым товарам.",
            "Подтвердите срок поставки по заявке заказчика и наличие товара на складе.",
            "Включены ли доставка и разгрузка до адреса заказчика в цену предложения?",
            "Есть ли отклонения от характеристик ТЗ или предлагаемые аналоги?",
        ]
    )
    return _dedupe_text_items(questions)


def _build_goods_rfq_payload(metadata: dict[str, Any], documents: list[AnalyzedDocument]) -> dict[str, Any]:
    """Backward-compatible RFQ document projection facade."""
    return build_goods_rfq_payload(metadata, documents, _collect_goods_supply_items_from_documents=_collect_goods_supply_items_from_documents)


def _build_goods_economics_payload(
    metadata: dict[str, Any],
    documents: list[AnalyzedDocument],
    analysis_mode: str,
    economics: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compatibility facade for operator economics; preserve legacy inputs."""
    return build_goods_economics_payload(
        metadata,
        documents,
        analysis_mode,
        economics,
        collect_goods_items=_collect_goods_supply_items_from_documents,
        extract_notice_price=_extract_notice_price,
        collect_role_text=_collect_role_text,
        parse_float=_parse_float,
        format_decimal_price=_format_decimal_price,
    )


def _build_document_grounded_requirements(documents: list[AnalyzedDocument], procurement_kind: str) -> list[dict[str, str]]:
    """Backward-compatible RFQ document projection facade."""
    return build_document_grounded_requirements(documents, procurement_kind, _build_goods_requirement_rows=_build_goods_requirement_rows, _cleanup_tabular_value=_cleanup_tabular_value, _extract_meaningful_snippets=_extract_meaningful_snippets)


def _build_document_grounded_questions(procurement_kind: str, documents: list[AnalyzedDocument]) -> list[str]:
    """Backward-compatible RFQ document projection facade."""
    return build_document_grounded_questions(procurement_kind, documents, _build_goods_questions=_build_goods_questions, _collect_supply_items=_collect_supply_items, _is_vehicle_maintenance_services=_is_vehicle_maintenance_services, _service_okpd2_from_sources=_service_okpd2_from_sources)






def _build_document_grounded_risks(procurement_kind: str, documents: list[AnalyzedDocument], contract_text: str) -> list[dict[str, str]]:
    """Backward-compatible RFQ document projection facade."""
    return project_document_grounded_risks(procurement_kind, documents, contract_text, _collect_supply_items=_collect_supply_items, _is_vehicle_maintenance_services=_is_vehicle_maintenance_services, _service_okpd2_from_sources=_service_okpd2_from_sources)


def _build_document_grounded_rfq_sections(procurement_kind: str) -> list[str]:
    return build_document_grounded_rfq_sections(procurement_kind)


def _build_goods_preliminary_analysis(*, metadata: dict[str, Any], documents: list[AnalyzedDocument], technical_spec_text: str, contract_draft_text: str, notice_text: str) -> dict[str, Any]:
    """Compatibility facade preserving source-monolith runtime overrides."""
    return project_build_goods_preliminary_analysis(metadata=metadata, documents=documents, technical_spec_text=technical_spec_text, contract_draft_text=contract_draft_text, notice_text=notice_text, _cleanup_delivery_address=_cleanup_delivery_address, _cleanup_tabular_value=_cleanup_tabular_value, _collect_goods_supply_items_from_documents=_collect_goods_supply_items_from_documents, _dedupe_text_items=_dedupe_text_items, _extract_goods_spec_table=_extract_goods_spec_table, _extract_inline_goods_field=_extract_inline_goods_field, _extract_notice_delivery_deadline=_extract_notice_delivery_deadline, _extract_notice_price=_extract_notice_price, _match_first=_match_first, _match_first_dotall=_match_first_dotall, _normalize_analysis_sentence=_normalize_analysis_sentence, _parse_float=_parse_float, _shorten_acceptance_terms=_shorten_acceptance_terms, _shorten_payment_terms=_shorten_payment_terms, _supply_item_to_row=_supply_item_to_row)


def _build_preliminary_procurement_analysis(*, metadata: dict[str, Any], documents: list[AnalyzedDocument], technical_spec_text: str, contract_draft_text: str, notice_text: str) -> dict[str, Any]:
    """Compatibility facade with runtime-bound dependencies."""
    return project_build_preliminary_procurement_analysis(metadata=metadata, documents=documents, technical_spec_text=technical_spec_text, contract_draft_text=contract_draft_text, notice_text=notice_text, _build_goods_preliminary_analysis=_build_goods_preliminary_analysis, _build_services_preliminary_analysis=_build_services_preliminary_analysis, _build_software_work_rows=_build_software_work_rows, _build_supply_rows=_build_supply_rows, _classify_procurement_scope=_classify_procurement_scope, _cleanup_tabular_value=_cleanup_tabular_value, _collect_matches=_collect_matches, _collect_supply_items=_collect_supply_items, _dedupe_text_items=_dedupe_text_items, _extract_notice_delivery_deadline=_extract_notice_delivery_deadline, _extract_notice_price=_extract_notice_price, _extract_notice_service_deadline=_extract_notice_service_deadline, _format_money_value=_format_money_value, _match_first=_match_first, _match_first_dotall=_match_first_dotall, _normalize_analysis_sentence=_normalize_analysis_sentence, _rewrite_compliance_highlight=_rewrite_compliance_highlight, _rewrite_delivery_model_item=_rewrite_delivery_model_item, _shorten_acceptance_terms=_shorten_acceptance_terms, _shorten_payment_terms=_shorten_payment_terms, build_software_preliminary_analysis=build_software_preliminary_analysis, build_training_location_action=build_training_location_action, extract_training_candidate_facts=extract_training_candidate_facts, re=re)


def _normalize_supplier_questions(questions: list[dict[str, Any]], procurement_kind: str) -> list[str]:
    """Backward-compatible upload service facade."""
    return normalize_supplier_questions(questions, procurement_kind, translate_user_text=_translate_user_text)


def delivery_address_from_preliminary(preliminary_analysis: dict[str, Any]) -> str | None:
    for item in preliminary_analysis.get("overview", []):
        if str(item).startswith("Адрес поставки:"):
            return str(item).split(":", 1)[1].strip() or None
    return None


def _build_output_payloads(*, metadata: dict[str, Any], documents: list[AnalyzedDocument], analysis_mode: str, requirements: dict[str, Any], calibrated_risks: list[dict[str, Any]], supplier_questions: list[dict[str, Any]], tkp_comparison: dict[str, Any] | None, economics: dict[str, Any] | None, bid_decision: dict[str, Any] | None, core_complete: bool, quote_inputs_present: bool) -> dict[str, dict[str, Any]]:
    """Compatibility facade binds product output dependencies at call time."""
    return project_build_output_payloads(metadata=metadata, documents=documents, analysis_mode=analysis_mode, requirements=requirements, calibrated_risks=calibrated_risks, supplier_questions=supplier_questions, tkp_comparison=tkp_comparison, economics=economics, bid_decision=bid_decision, core_complete=core_complete, quote_inputs_present=quote_inputs_present, _build_document_grounded_questions=_build_document_grounded_questions, _build_document_grounded_requirements=_build_document_grounded_requirements, _build_document_grounded_rfq_sections=_build_document_grounded_rfq_sections, _build_document_grounded_risks=_build_document_grounded_risks, _build_goods_economics_payload=_build_goods_economics_payload, _build_goods_rfq_payload=_build_goods_rfq_payload, _build_preliminary_procurement_analysis=_build_preliminary_procurement_analysis, _classify_procurement_scope=_classify_procurement_scope, _collect_role_text=_collect_role_text, _collect_supply_items=_collect_supply_items, _collect_unmerged_source_items=_collect_unmerged_source_items, _extract_notice_price=_extract_notice_price, _extract_requirement_rows=_extract_requirement_rows, _is_goods_supply_table_present=_is_goods_supply_table_present, _normalize_supplier_questions=_normalize_supplier_questions, _safe_datetime=_safe_datetime, _service_okpd2_from_sources=_service_okpd2_from_sources, _translate_user_text=_translate_user_text, build_complete_goods_positions=build_complete_goods_positions, build_non_goods_economics_payload=build_non_goods_economics_payload, build_operator_analysis_trace=build_operator_analysis_trace, build_operator_requirements_context=build_operator_requirements_context, build_operator_risk_payload=build_operator_risk_payload, build_operator_tender_summary=build_operator_tender_summary, build_provisional_operator_recommendation=build_provisional_operator_recommendation, build_quote_comparison_report=build_quote_comparison_report, candidate_requirement_rows=candidate_requirement_rows, candidate_rfq_sections=candidate_rfq_sections, candidate_risks=candidate_risks, candidate_supplier_questions=candidate_supplier_questions, delivery_address_from_preliminary=delivery_address_from_preliminary, detect_procurement_richness=detect_procurement_richness, extract_contract_term_facts=extract_contract_term_facts, extract_goods_source_facts=extract_goods_source_facts, semantic_procurement_role=semantic_procurement_role, submission_deadline_from_metadata=submission_deadline_from_metadata)






def _document_type_label(item: dict[str, Any]) -> str:
    return document_type_label(item)


def _build_downloaded_documents_inventory(metadata: dict[str, Any]) -> list[dict[str, str]]:
    return build_downloaded_documents_inventory(metadata)


def _build_steps_from_outputs(metadata: dict[str, Any], outputs: dict[str, dict[str, Any]]) -> list[DemoStep]:
    """Compatibility facade to the isolated, deterministic step projector."""
    from src.modules.tender_operator_agent_demo.operator_step_projection import (
        build_operator_steps,
    )

    return build_operator_steps(metadata, outputs)


def _build_final_recommendation(outputs: dict[str, dict[str, Any]]) -> DemoFinalRecommendation:
    final_recommendation = outputs["final_recommendation"]
    return DemoFinalRecommendation(
        recommendation=DemoRecommendationCode(final_recommendation["recommendation"]),
        label=final_recommendation["label"],
        rationale=final_recommendation["rationale"],
        key_requirements=final_recommendation["key_requirements"],
        open_questions=final_recommendation["open_questions"],
        risks=final_recommendation["risks"],
        economics=final_recommendation["economics"],
        manual_checks=final_recommendation["manual_checks"],
        trace=outputs["trace"]["overall_explanation"],
    )


def _preliminary_analysis_supply_section_title(preliminary_analysis: dict[str, Any]) -> str:
    from src.modules.tender_operator_agent_demo.operator_report_markdown import (
        preliminary_supply_section_title,
    )
    return preliminary_supply_section_title(preliminary_analysis)


def _preliminary_analysis_supply_section_markdown(preliminary_analysis: dict[str, Any]) -> str:
    from src.modules.tender_operator_agent_demo.operator_report_markdown import (
        preliminary_supply_section_markdown,
    )
    return preliminary_supply_section_markdown(preliminary_analysis)


def _build_report_markdown(metadata: dict[str, Any], outputs: dict[str, dict[str, Any]]) -> str:
    from src.modules.tender_operator_agent_demo.operator_report_markdown import (
        render_operator_report_markdown,
    )
    return render_operator_report_markdown(
        metadata, outputs,
        inventory_builder=_build_downloaded_documents_inventory,
        supply_title=_preliminary_analysis_supply_section_title,
        supply_markdown=_preliminary_analysis_supply_section_markdown,
    )


def _render_report_html(metadata: dict[str, Any], outputs: dict[str, dict[str, Any]]) -> str:
    """Compatibility facade delegating legacy HTML to the presentation module."""
    from src.modules.tender_operator_agent_demo.operator_legacy_html_renderer import (
        render_legacy_report_html,
    )

    return render_legacy_report_html(
        metadata,
        outputs,
        inventory_builder=_build_downloaded_documents_inventory,
        supply_section_title=_preliminary_analysis_supply_section_title,
        input_dir_resolver=get_demo_run_input_dir,
    )


def _normalize_report_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _is_missing_metadata_value(value: Any) -> bool:
    if value is None:
        return True
    text = _normalize_report_text(str(value))
    return not text or text.lower() in {"не указан", "none", "null", "n/a", "—"}


def _extract_customer_name_from_text(*texts: str | None) -> str | None:
    """Legacy positional wrapper around the role-evidence customer resolver.

    Historical call order is ``(combined, notice, contract, technical_spec,
    *supporting)``.  Role-specific texts keep their authority; the combined
    text is only a lowest-priority fallback for explicit customer-role
    patterns.  Generic unscoped organization names are never promoted.
    """

    from src.modules.tender_operator_agent_demo.customer_role_facts import (
        resolve_customer_name,
    )

    padded = (*texts, None, None, None, None, None)
    combined_text, notice_text, contract_draft_text, technical_spec_text = padded[:4]
    supporting = tuple(item for item in padded[4:] if item)
    if len(texts) == 1:
        # Single-text callers (mostly tests) get the full explicit-pattern
        # set against that one source.
        resolution = resolve_customer_name(combined_text=texts[0])
    else:
        resolution = resolve_customer_name(
            notice_text=notice_text,
            contract_draft_text=contract_draft_text,
            technical_spec_text=technical_spec_text,
            supporting_texts=supporting,
            combined_text=combined_text,
        )
    return resolution.value if resolution is not None else None


def _extract_updated_date_from_text(*texts: str | None) -> str | None:
    for raw_text in texts:
        if not raw_text:
            continue
        match = re.search(r"<(?:\w+:)?directDT>(\d{4})-(\d{2})-(\d{2})T", raw_text)
        if match:
            return f"{match.group(3)}.{match.group(2)}.{match.group(1)}"
        match = re.search(r"(?im)обновлено\s*[:\-]?\s*(\d{2}\.\d{2}\.\d{4})", raw_text)
        if match:
            return match.group(1)
    return None


def _enrich_procurement_metadata_from_documents(
    metadata: dict[str, Any],
    *,
    documents: list[AnalyzedDocument] | None = None,
    combined_text: str | None = None,
    notice_text: str | None,
    technical_spec_text: str | None,
    contract_draft_text: str | None,
) -> dict[str, Any]:
    """Legacy API retained while metadata merging lives in one product module."""
    from src.modules.tender_operator_agent_demo.operator_metadata_enrichment import (
        enrich_procurement_metadata,
    )

    return enrich_procurement_metadata(
        metadata,
        documents=documents,
        combined_text=combined_text,
        notice_text=notice_text,
        technical_spec_text=technical_spec_text,
        contract_draft_text=contract_draft_text,
        missing_value=_is_missing_metadata_value,
        updated_date_from_text=_extract_updated_date_from_text,
    )


def _render_canonical_report_html(model: dict[str, Any]) -> str:
    """Presentation-only web renderer for the canonical report model."""
    return _render_product_report_html(model, customer=False)


def _render_customer_report_html(model: dict[str, Any]) -> str:
    """Customer projection deliberately excludes operational report metadata."""
    return _render_product_report_html(model)


def _render_product_report_html(model: dict[str, Any], *, customer: bool=True) -> str:
    """Legacy renderer and analysis compatibility facade."""
    return project_render_product_report_html(model, customer=customer)


def _persist_outputs(run_id: str, metadata: dict[str, Any], outputs: dict[str, dict[str, Any]], steps: list[DemoStep]) -> None:
    from src.modules.procurement_analysis.frozen_producer import (
        persist_frozen_r7_outputs,
    )
    renderer = _render_customer_report_html if metadata.get("analysis_mode") == "production_llm_r10_1" else _render_canonical_report_html
    persist_frozen_r7_outputs(output_dir=_output_dir(run_id), run_id=run_id, metadata=metadata, outputs=outputs, steps=steps, render_html=renderer, now_factory=_safe_datetime)


def _render_procurement_blocked_report_html(metadata: dict[str, Any]) -> str:
    """Legacy renderer and analysis compatibility facade."""
    return project_render_procurement_blocked_report_html(metadata)


def _ensure_procurement_blocked_report_html(run_id: str) -> Path | None:
    path = _report_html_path(run_id)
    if path.is_file():
        return path
    metadata = _load_metadata(run_id)
    if metadata.get("mode") != "procurement_search_intake" or metadata.get("files"):
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_procurement_blocked_report_html(metadata), encoding="utf-8")
    return path


def analyze_uploaded_demo_run(run_id: str) -> TenderOperatorUploadedRunAnalyzeResponse:
    metadata = _load_metadata(run_id)
    # A successful manual retry must not present errors from an earlier attempt
    # as if they described the current document analysis. Historical failure
    # events stay in the immutable run event feed for operator audit.
    was_failed = metadata.get("status") == TenderOperatorUploadedRunStatus.FAILED.value
    has_stale_error = any(
        str(item).startswith("Analysis failed safely: ")
        for item in metadata.get("warnings", [])
    )
    if was_failed or has_stale_error:
        previous_status = str(metadata.get("status") or "unknown")
        metadata["warnings"] = [
            item for item in metadata.get("warnings", [])
            if not str(item).startswith("Analysis failed safely: ")
        ]
        metadata["limitations"] = [
            item for item in metadata.get("limitations", [])
            if item != "Fallback report generation failed. Manual operator review required."
        ]
        append_demo_run_event(
            run_id,
            "analysis_retry_started",
            "Повторная обработка сохранённых оригиналов после предыдущей ошибки.",
            {"previous_status": previous_status},
        )
    if not metadata.get("files") and metadata.get("status") == TenderOperatorUploadedRunStatus.DOCS_REQUIRED.value:
        metadata["analysis_status"] = "blocked"
        _save_metadata(run_id, metadata)
        append_demo_run_event(
            run_id,
            "analysis_blocked",
            "Анализ остановлен: документация не получена автоматически, требуется ручная загрузка.",
            {"status": metadata.get("status")},
        )
        raise HTTPException(status_code=409, detail="Документация ещё не загружена. Добавьте файлы вручную и повторите анализ.")

    metadata["status"] = TenderOperatorUploadedRunStatus.ANALYZING.value
    metadata["analysis_mode"] = "analyzing"
    metadata["analysis_status"] = "analyzing"
    _save_metadata(run_id, metadata)
    append_demo_run_event(
        run_id,
        "analysis_started",
        "Запущен контролируемый анализ локального demo-run.",
        {"mode": metadata.get("mode"), "files": len(metadata.get("files", []))},
    )

    try:
        ai_provenance = _runtime_ai_provenance()
        documents = _collect_documents(run_id, metadata)
        warnings = list(dict.fromkeys(metadata.get("warnings", []) + [warning for doc in documents for warning in doc.warnings]))

        notice_text = _collect_role_text(documents, "notice") or _collect_role_text(documents, "supporting") or metadata["tender_title"]
        technical_spec_text = _collect_role_text(documents, "technical_spec")
        contract_draft_text = _collect_role_text(documents, "contract_draft")
        combined_text = "\n\n".join(doc.text for doc in documents if doc.text)
        quote_paths = _collect_quote_paths(run_id, metadata)
        spreadsheet_sources = _collect_spreadsheet_sources(documents)
        economics_inputs = metadata.get("economics_inputs", {})
        metadata = _enrich_procurement_metadata_from_documents(
            metadata,
            documents=documents,
            combined_text=combined_text,
            notice_text=notice_text,
            technical_spec_text=technical_spec_text,
            contract_draft_text=contract_draft_text,
        )
        from src.modules.tender_operator_agent_demo.operator_notice_revision import (
            selected_archived_notice_text,
        )

        # Avoid passing an obsolete first-file notice into LLM/preliminary analysis
        # after a newer exact registry-matched archival revision was selected.
        selected_notice_text = selected_archived_notice_text(
            documents, metadata.get("notice_revision_selected")
        )
        if selected_notice_text:
            notice_text = selected_notice_text

        profile = None if metadata.get("mode") == "procurement_search_intake" else get_supplier_profile()
        doc_relevance = score_procurement_document_text(text=combined_text or "", profile=profile)
        metadata["document_relevance"] = doc_relevance
        append_demo_run_event(
            run_id,
            "relevance_document_scoring_completed",
            f"Скоринг документов выполнен: найдено {len(doc_relevance.get('document_matched_terms', []))} совпадений.",
            {"document_score": doc_relevance.get("document_score")},
        )

        from src.modules.tender_operator_agent_demo.eis_notice_parser import (
            build_notice_priority_prompt_section,
            build_technical_documents_prompt_section,
        )
        procurement = metadata.get("procurement", {})
        priority_section = build_notice_priority_prompt_section(procurement)
        if priority_section and notice_text:
            notice_text = priority_section + "\n\n" + notice_text
        technical_docs_section = build_technical_documents_prompt_section(metadata.get("files", []))
        if technical_docs_section:
            technical_spec_text = technical_docs_section + "\n\n" + (technical_spec_text or "")

        core_complete = bool(technical_spec_text and contract_draft_text and notice_text)
        if not technical_spec_text and combined_text:
            technical_spec_text = combined_text[:6000]
            warnings.append("Технические документы не выделены отдельно; используется общий текст документов.")
        if not contract_draft_text:
            warnings.append("Contract draft text was not fully extracted; contract risks are partially inferred.")

        provider_mode = "llm"
        llm_result = _try_run_llm_workflow(
            run_id=run_id,
            notice_text=notice_text,
            technical_spec_text=technical_spec_text,
            contract_draft_text=contract_draft_text,
            quote_paths=quote_paths,
            provider_mode=provider_mode,
        )
        if llm_result is not None:
            llm_classification = _classify_controlled_llm_result(llm_result)
            failed_sections = llm_classification["failed_sections"]
            llm_validation_failed = llm_classification["event_type"] != "llm_analysis_completed"
            ai_provenance.update(
                {
                    "analysis_engine": llm_classification["analysis_engine"],
                    "llm_invoked": True,
                    "llm_calls_count": llm_classification["llm_calls_count"],
                    "fallback_reason": llm_classification["fallback_reason"],
                }
            )
            requirements = llm_result.get("requirements", {})
            calibrated_risks = llm_result.get("contract_risks", [])
            supplier_questions = llm_result.get("supplier_questions", [])
            rfq_draft = llm_result.get("rfq_draft", {})
            analysis_mode = llm_classification["analysis_mode"]
            if llm_validation_failed:
                warnings.append(
                    (
                        "Контролируемый LLM-анализ не прошёл валидацию для разделов: "
                        + ", ".join(failed_sections)
                        if failed_sections
                        else "Контролируемый LLM-анализ не предоставил сведения о валидации разделов"
                    )
                    + ". Невалидированные результаты не приняты."
                )
            append_demo_run_event(
                run_id,
                llm_classification["event_type"],
                (
                    f"LLM-анализ выполнен через {llm_result.get('resolved_provider', 'llm')}."
                    if not llm_validation_failed
                    else "Контролируемый LLM-анализ завершён с ошибками валидации; "
                    "невалидированные результаты не приняты."
                ),
                {
                    "analysis_mode": analysis_mode,
                    "resolved_provider": llm_result.get("resolved_provider"),
                    "failed_sections": failed_sections,
                    "trace_ids": llm_result.get("trace_ids", []),
                },
            )
        else:
            requirements = {
                "technical_requirements": [],
                "document_requirements": [],
                "qualification_requirements": [],
                "evaluation_criteria": [],
            }
            calibrated_risks = []
            supplier_questions = []
            rfq_draft = {}
            analysis_mode = "fallback_deterministic_adapter"
            # Availability of the Data Platform and a local model socket does
            # not mean this particular controlled workflow invoked a model.
            # Expose the effective mode honestly instead of silently hiding
            # a broad validation/runtime exception as a successful AI run.
            provider_config = str(get_settings().llm_provider or "").lower()
            fallback_reason = (
                "configured_stub_provider"
                if provider_config == "stub"
                else "controlled_llm_workflow_unavailable"
            )
            ai_provenance["analysis_engine"] = "deterministic"
            ai_provenance["llm_invoked"] = False
            ai_provenance["llm_calls_count"] = 0
            ai_provenance["fallback_reason"] = fallback_reason
            append_demo_run_event(
                run_id,
                "stub_analysis_fallback",
                "Полный LLM-анализ не выполнялся; итог включает только ограниченное "
                "детерминированное извлечение и требует проверки специалистом.",
                {"core_complete": core_complete, "fallback_reason": fallback_reason},
            )
        metadata["ai_runtime_provenance"] = ai_provenance

        spreadsheet_comparison = build_quote_comparison(spreadsheet_sources, analysis_mode)
        if spreadsheet_comparison.supplier_quotes_found:
            tkp_comparison = _serialize_quote_comparison(spreadsheet_comparison)
            economics_summary = build_economics_summary(
                quote_comparison=spreadsheet_comparison,
                analysis_mode=analysis_mode,
                target_margin_percent=float(economics_inputs.get("target_margin_percent", DEFAULT_TARGET_MARGIN_PERCENT)),
                logistics_reserve_percent=float(economics_inputs.get("logistics_reserve_percent", DEFAULT_LOGISTICS_RESERVE_PERCENT)),
                risk_reserve_percent=float(economics_inputs.get("risk_reserve_percent", DEFAULT_RISK_RESERVE_PERCENT)),
                payment_delay_days=int(economics_inputs.get("payment_delay_days", DEFAULT_PAYMENT_DELAY_DAYS)),
            )
            economics = _serialize_economics_summary(economics_summary)
        else:
            tkp_comparison = None
            economics = None
        bid_decision = llm_result.get("bid_decision") if llm_result else None

        supplier_search_outcome = _run_supplier_internet_search(
            tender_title=metadata.get("tender_title", ""),
            notice_text=notice_text,
            technical_spec_text=technical_spec_text,
        )
        metadata["supplier_search"] = {
            "query": supplier_search_outcome.query_used,
            "total_found": supplier_search_outcome.total_found,
            "suppliers": [
                {"name": s.name, "site": s.site, "snippet": s.snippet[:200], "signals": s.relevance_signals}
                for s in supplier_search_outcome.suppliers
            ],
        }
        if supplier_search_outcome.error:
            append_demo_run_event(run_id, "supplier_search_warning", f"Поиск поставщиков недоступен: {supplier_search_outcome.error}", {})
        elif supplier_search_outcome.total_found:
            append_demo_run_event(
                run_id, "supplier_search_completed", f"Найдено {supplier_search_outcome.total_found} потенциальных поставщиков.",
                {"query": supplier_search_outcome.query_used, "count": supplier_search_outcome.total_found},
            )

        limitations = list(dict.fromkeys(metadata.get("limitations", [])))
        if analysis_mode == "fallback_deterministic_adapter":
            limitations.append(
                "Полный LLM-анализ документов не выполнялся "
                f"({ai_provenance['fallback_reason']}). "
                "Доступность локальной модели или Data Platform не является "
                "подтверждением анализа закупки; детальные риски и экономика "
                "требуют отдельной проверки."
            )
        if not core_complete:
            limitations.append("Full runner integration was partially applied because the uploaded package did not produce all core extracted texts.")
        quote_inputs_present = bool(quote_paths or spreadsheet_sources)
        if not quote_inputs_present:
            limitations.append("TKP not uploaded. Supplier comparison and economics remain blocked or partial.")
        elif not spreadsheet_sources and quote_paths:
            limitations.append("Quote files were uploaded in non-spreadsheet format; structured comparison and economics require manual review or XLS/XLSX.")
        if spreadsheet_sources:
            limitations.append("Spreadsheet normalization uses deterministic heuristics and may require manual review for нестандартные таблицы.")
            if tkp_comparison:
                limitations.extend(tkp_comparison.get("limitations", []))
            if economics:
                limitations.extend(economics.get("limitations", []))
        elif any(item["extension"] in {".xlsx", ".xls"} for item in metadata.get("files", [])):
            limitations.append("Spreadsheet files were uploaded, but structured extraction could not start.")

        metadata["warnings"] = sorted(set(warnings))
        metadata["limitations"] = limitations
        metadata["analysis_mode"] = analysis_mode
        metadata["analysis_status"] = "completed"

        # Preserve the established public/patch-wrapper function signature.
        # Validated-schema LLM RFQ remains a review-only candidate, never an
        # authenticated factual source or an external communication.
        if analysis_mode == "llm_tender_operator_provider" and isinstance(rfq_draft, dict):
            requirements = {**requirements, "_unverified_llm_rfq_draft": rfq_draft}
        outputs = _build_output_payloads(
            metadata=metadata,
            documents=documents,
            analysis_mode=analysis_mode,
            requirements=requirements,
            calibrated_risks=calibrated_risks,
            supplier_questions=supplier_questions,
            tkp_comparison=tkp_comparison,
            economics=economics,
            bid_decision=bid_decision,
            core_complete=core_complete,
            quote_inputs_present=quote_inputs_present,
        )
        steps = _build_steps_from_outputs(metadata, outputs)
        final_recommendation = _build_final_recommendation(outputs)
        status = TenderOperatorUploadedRunStatus.COMPLETED if core_complete and tkp_comparison else TenderOperatorUploadedRunStatus.COMPLETED_WITH_WARNINGS
        if final_recommendation.recommendation == DemoRecommendationCode.MANUAL_REVIEW_REQUIRED:
            status = TenderOperatorUploadedRunStatus.COMPLETED_WITH_WARNINGS if quote_inputs_present else TenderOperatorUploadedRunStatus.NEEDS_REVIEW

        metadata["status"] = status.value
        _save_metadata(run_id, metadata)
        _persist_outputs(run_id, metadata, outputs, steps)
        append_demo_run_event(
            run_id,
            "analysis_completed",
            "Анализ завершён в контролируемом demo-контуре.",
            {"status": status.value, "analysis_mode": analysis_mode},
        )

        return TenderOperatorUploadedRunAnalyzeResponse(
            run_id=run_id,
            status=status,
            analysis_mode=analysis_mode,
            warnings=metadata["warnings"],
            limitations=metadata["limitations"],
            steps=steps,
            final_recommendation=final_recommendation,
        )
    except HTTPException:
        raise
    except Exception as exc:
        metadata["status"] = TenderOperatorUploadedRunStatus.FAILED.value
        metadata["analysis_mode"] = "failed"
        metadata["analysis_status"] = "failed"
        metadata["warnings"] = list(dict.fromkeys(metadata.get("warnings", []) + [f"Analysis failed safely: {exc}"]))
        metadata["limitations"] = list(dict.fromkeys(metadata.get("limitations", []) + ["Fallback report generation failed. Manual operator review required."]))
        _save_metadata(run_id, metadata)
        append_demo_run_event(
            run_id,
            "analysis_blocked",
            "Анализ завершился безопасной остановкой из-за внутренней ошибки.",
            {"error": str(exc)},
        )

        failed_outputs = {
            "final_recommendation": {
                "recommendation": DemoRecommendationCode.MANUAL_REVIEW_REQUIRED.value,
                "label": "нужна ручная проверка",
                "rationale": ["Анализ не завершился полностью и был остановлен в безопасном режиме."],
                "key_requirements": ["Проверка пакета документов вручную"],
                "open_questions": ["Нужно повторно проверить загруженные файлы и формат документов."],
                "risks": ["Автоматический анализ не завершён"],
                "economics": ["Недостаточно данных"],
                "manual_checks": ["Повторно просмотреть пакет документов вручную."],
            },
            "trace": {
                "overall_explanation": "Система не выполнила внешних действий и остановила анализ в безопасном режиме после внутренней ошибки.",
                "per_step": {step: "Анализ остановлен в safe mode." for step in ("documents", "requirements", "supplier_search", "questions", "rfq", "quotes", "economics", "risks", "decision")},
                "limitations": metadata["limitations"],
            },
        }
        final_recommendation = _build_final_recommendation(failed_outputs)
        steps = [
            DemoStep(
                key="documents",
                order=1,
                title="Документы",
                short_title="Документы",
                status=DemoStepStatus.NEEDS_REVIEW,
                description="Анализ остановлен до полного прохождения pipeline.",
                agent_action="Система сохранила локальные файлы, но не завершила разбор.",
                result_summary="Run остановлен в safe mode.",
                findings=metadata["warnings"],
                human_review=["Проверить формат и содержимое загруженных файлов вручную."],
                trace="Безопасная остановка без внешних действий.",
                result_sections=[],
            )
        ]
        return TenderOperatorUploadedRunAnalyzeResponse(
            run_id=run_id,
            status=TenderOperatorUploadedRunStatus.FAILED,
            analysis_mode="failed",
            warnings=metadata["warnings"],
            limitations=metadata["limitations"],
            steps=steps,
            final_recommendation=final_recommendation,
        )


def _report_json_path(run_id: str) -> Path:
    return _output_dir(run_id) / "report.json"


def _report_html_path(run_id: str) -> Path:
    return _output_dir(run_id) / "report.html"


def _load_report_json(run_id: str) -> dict[str, Any]:
    path = _report_json_path(run_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Report is not available yet")
    return _read_json(path)


def get_uploaded_demo_run(run_id: str) -> TenderOperatorUploadedRunResponse:
    """Stable run retrieval facade with runtime-bound helper compatibility."""
    from src.modules.tender_operator_agent_demo.operator_run_retrieval import (
        project_uploaded_run,
    )

    return project_uploaded_run(
        run_id,
        _load_metadata=_load_metadata,
        DemoStep=DemoStep,
        DemoFinalRecommendation=DemoFinalRecommendation,
        _output_dir=_output_dir,
        _read_json=_read_json,
        _build_final_recommendation=_build_final_recommendation,
        _load_report_json=_load_report_json,
        DemoStepStatus=DemoStepStatus,
        _coerce_quote_comparison_payload=_coerce_quote_comparison_payload,
        _coerce_economics_summary_payload=_coerce_economics_summary_payload,
        _report_html_path=_report_html_path,
        _ensure_procurement_blocked_report_html=_ensure_procurement_blocked_report_html,
        TenderOperatorUploadedRunResponse=TenderOperatorUploadedRunResponse,
        datetime=datetime,
        TenderOperatorUploadedRunStatus=TenderOperatorUploadedRunStatus,
        TenderOperatorUploadedFile=TenderOperatorUploadedFile,
        load_demo_run_events=load_demo_run_events,
    )


def get_uploaded_demo_run_steps(run_id: str) -> TenderOperatorUploadedRunStepsResponse:
    steps_path = _output_dir(run_id) / "steps.json"
    metadata = _load_metadata(run_id)
    if not steps_path.is_file():
        return TenderOperatorUploadedRunStepsResponse(
            run_id=run_id,
            status=TenderOperatorUploadedRunStatus(metadata["status"]),
            steps=[],
        )
    payload = _read_json(steps_path)
    return TenderOperatorUploadedRunStepsResponse(
        run_id=run_id,
        status=TenderOperatorUploadedRunStatus(metadata["status"]),
        steps=[DemoStep.model_validate(item) for item in payload.get("steps", [])],
    )


def save_uploaded_demo_steps(run_id: str, steps: list[DemoStep]) -> None:
    _write_json(_output_dir(run_id) / "steps.json", {"steps": [item.model_dump(mode="json") for item in steps]})


def get_uploaded_demo_report(run_id: str) -> TenderOperatorDemoReportResponse:
    payload = _load_report_json(run_id)
    return TenderOperatorDemoReportResponse.model_validate(payload)


def get_uploaded_demo_report_download(run_id: str) -> FileResponse:
    path = _ensure_procurement_blocked_report_html(run_id) or _report_html_path(run_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Report HTML is not available yet")
    return FileResponse(path, media_type="text/html; charset=utf-8", filename=f"{run_id}_report.html")


def get_uploaded_demo_report_html(run_id: str) -> str:
    path = _ensure_procurement_blocked_report_html(run_id) or _report_html_path(run_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Report HTML is not available yet")
    return path.read_text(encoding="utf-8")


def get_uploaded_demo_source_file_download(run_id: str, file_id: str) -> FileResponse:
    metadata = _load_metadata(run_id)
    descriptor = next((item for item in metadata.get("files", []) if item.get("file_id") == file_id), None)
    if descriptor is None:
        raise HTTPException(status_code=404, detail="Source file was not found")
    input_dir = get_demo_run_input_dir(run_id).resolve()
    target = (input_dir / str(descriptor.get("stored_name") or "")).resolve()
    if input_dir not in target.parents and target != input_dir:
        raise HTTPException(status_code=400, detail="Invalid stored file path")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Stored source file is not available")
    return FileResponse(
        target,
        media_type=str(descriptor.get("content_type") or "application/octet-stream"),
        filename=str(descriptor.get("original_name") or descriptor.get("display_name") or target.name),
    )


def get_uploaded_demo_archive_download(run_id: str) -> FileResponse:
    path = get_demo_run_input_dir(run_id) / "documentation-archive.zip"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Documentation archive is not available")
    return FileResponse(path, media_type="application/zip", filename="documentation-archive.zip")
