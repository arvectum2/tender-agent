from __future__ import annotations

from typing import Any

from src.modules.hermes_agent.schemas import (
    HermesAnalysisResponse,
    HermesQualityCheck,
    NmckMappingResult,
    NormalizedLineItem,
)


QUALITY_GATES = [
    "line_items_required_for_goods",
    "line_items_required_if_specification_exists",
    "summary_subject_not_too_generic",
    "evidence_required_for_high_confidence",
    "all_documents_used",
]


def _has_goods_indicators(analysis: HermesAnalysisResponse) -> bool:
    roles_lower = [r.lower() for r in analysis.document_roles]
    goods_roles = {"specification", "technical_specification", "спецификация", "тз",
                   "nmck_calculation", "appendix"}
    for r in roles_lower:
        for gr in goods_roles:
            if gr in r:
                return True
    subject_lower = analysis.summary.subject.lower().strip()
    if any(kw in subject_lower for kw in ("кабель", "провод", "труб", "оборудован", "материал")):
        return True
    return False


def check_line_items_required_for_goods(analysis: HermesAnalysisResponse) -> HermesQualityCheck:
    is_goods = _has_goods_indicators(analysis)
    if not analysis.line_items and is_goods:
        return HermesQualityCheck(
            check_name="line_items_required_for_goods",
            status="failed",
            message="Line items are empty but documents indicate goods procurement.",
        )
    if not analysis.line_items and not is_goods:
        return HermesQualityCheck(
            check_name="line_items_required_for_goods",
            status="passed",
            message="No goods indicators found, line items not required.",
        )
    return HermesQualityCheck(
        check_name="line_items_required_for_goods",
        status="passed",
        message=f"Found {len(analysis.line_items)} line item(s).",
    )


def check_line_items_required_if_specification_exists(analysis: HermesAnalysisResponse) -> HermesQualityCheck:
    roles_lower = [r.lower() for r in analysis.document_roles]
    has_spec = any("specification" in r or "technical_specification" in r for r in roles_lower)
    if has_spec and not analysis.line_items:
        return HermesQualityCheck(
            check_name="line_items_required_if_specification_exists",
            status="failed",
            message="Specification exists but no line items extracted.",
        )
    return HermesQualityCheck(
        check_name="line_items_required_if_specification_exists",
        status="passed",
        message="Line items present when specification exists." if has_spec else "No specification in document roles.",
    )


GENERIC_SUBJECT_EXACT = [
    "поставка", "выполнение", "оказание", "товар", "услуга", "работа",
    "поставка товара", "оказание услуг", "выполнение работ",
    "электротехническая продукция", "продукция", "материалы",
    "оборудование", "строительство", "ремонт", "обслуживание",
]

GENERIC_SUBJECT_PREFIXES = [
    "поставка", "выполнение", "оказание", "строительство", "ремонт",
]


def _is_generic_subject(subject: str) -> bool:
    """One canonical rule for both Hermes quality and readiness decisions."""
    if not subject:
        return True
    if subject in GENERIC_SUBJECT_EXACT:
        return True
    words = subject.split()
    if len(words) <= 3:
        for prefix in GENERIC_SUBJECT_PREFIXES:
            if subject.startswith(prefix):
                rest = subject[len(prefix):].strip()
                if not rest or len(rest.split()) <= 2:
                    return True
    return False


def check_summary_subject_not_too_generic(analysis: HermesAnalysisResponse) -> HermesQualityCheck:
    subject_lower = analysis.summary.subject.lower().strip()

    is_generic = _is_generic_subject(subject_lower)

    if is_generic and not analysis.line_items:
        return HermesQualityCheck(
            check_name="summary_subject_not_too_generic",
            status="failed",
            message=f"Subject '{analysis.summary.subject}' is too generic and no line items found.",
        )
    return HermesQualityCheck(
        check_name="summary_subject_not_too_generic",
        status="passed",
        message="Subject is adequately specific or line items are present.",
    )


def check_evidence_required_for_high_confidence(analysis: HermesAnalysisResponse) -> HermesQualityCheck:
    issues: list[str] = []
    for idx, item in enumerate(analysis.line_items):
        if item.confidence > 0.5 and (not item.source_document or not item.source_quote):
            issues.append(f"line_items[{idx}]: confidence={item.confidence} but missing source_document or source_quote")

    for idx, tr in enumerate(analysis.technical_requirements):
        if tr.confidence > 0.5 and (not tr.source_document or not tr.source_quote):
            issues.append(f"technical_requirements[{idx}]: confidence={tr.confidence} but missing evidence")

    status = "failed" if issues else "passed"
    return HermesQualityCheck(
        check_name="evidence_required_for_high_confidence",
        status=status,
        message="; ".join(issues) if issues else "All high-confidence fields have source evidence.",
    )


def check_all_documents_used(analysis: HermesAnalysisResponse) -> HermesQualityCheck:
    source_docs = set()
    for item in analysis.line_items:
        if item.source_document:
            source_docs.add(item.source_document)
    for tr in analysis.technical_requirements:
        if tr.source_document:
            source_docs.add(tr.source_document)
    for cr in analysis.certification_requirements:
        if cr.source_document:
            source_docs.add(cr.source_document)

    if not analysis.document_roles:
        return HermesQualityCheck(
            check_name="all_documents_used",
            status="passed",
            message="No document roles defined, skipping check.",
        )

    unused = [d for d in analysis.document_roles if d not in source_docs]
    if unused:
        return HermesQualityCheck(
            check_name="all_documents_used",
            status="warning",
            message=f"Documents not referenced in evidence: {', '.join(unused)}",
        )
    return HermesQualityCheck(
        check_name="all_documents_used",
        status="passed",
        message="All documents referenced in evidence.",
    )


def check_electrical_required_fields_present(
    analysis: HermesAnalysisResponse,
    normalized_items: list[NormalizedLineItem] | None = None,
) -> HermesQualityCheck:
    items = normalized_items or []
    if not items:
        return HermesQualityCheck(check_name="electrical_required_fields_present", status="passed", message="No normalized items to check.")
    missing = []
    for idx, item in enumerate(items):
        if not item.raw_name:
            missing.append(f"[{idx}] raw_name")
        if not item.normalized_name:
            missing.append(f"[{idx}] normalized_name")
    if missing:
        return HermesQualityCheck(
            check_name="electrical_required_fields_present",
            status="failed",
            message=f"Missing required fields: {', '.join(missing)}",
        )
    return HermesQualityCheck(check_name="electrical_required_fields_present", status="passed", message="All required fields present.")


def check_electrical_quantity_unit_required(
    analysis: HermesAnalysisResponse,
    normalized_items: list[NormalizedLineItem] | None = None,
) -> HermesQualityCheck:
    items = analysis.line_items
    if not items:
        return HermesQualityCheck(check_name="electrical_quantity_unit_required", status="passed", message="No line items to check.")
    missing = []
    for idx, item in enumerate(items):
        if not item.quantity:
            missing.append(f"[{idx}] quantity")
        if not item.unit:
            missing.append(f"[{idx}] unit")
    if missing:
        return HermesQualityCheck(
            check_name="electrical_quantity_unit_required",
            status="failed",
            message=f"Missing quantity/unit: {', '.join(missing)}",
        )
    return HermesQualityCheck(check_name="electrical_quantity_unit_required", status="passed", message="All items have quantity and unit.")


def check_electrical_cable_type_mark_required(
    analysis: HermesAnalysisResponse,
    normalized_items: list[NormalizedLineItem] | None = None,
) -> HermesQualityCheck:
    items = normalized_items or []
    cable_keywords = ["кабель", "провод", "сип"]
    if not items:
        return HermesQualityCheck(check_name="electrical_cable_type_mark_required", status="passed", message="No normalized items to check.")
    missing = []
    for idx, item in enumerate(items):
        raw_lower = item.raw_name.lower()
        is_cable = any(kw in raw_lower for kw in cable_keywords)
        if is_cable and not item.type_mark:
            missing.append(f"[{idx}] {item.raw_name}")
    if missing:
        return HermesQualityCheck(
            check_name="electrical_cable_type_mark_required",
            status="failed",
            message=f"Cable items missing type_mark: {', '.join(missing)}",
        )
    return HermesQualityCheck(check_name="electrical_cable_type_mark_required", status="passed", message="All cable items have type_mark.")


def check_electrical_standard_recommended(
    analysis: HermesAnalysisResponse,
    normalized_items: list[NormalizedLineItem] | None = None,
) -> HermesQualityCheck:
    items = normalized_items or []
    cable_keywords = ["кабель", "провод", "сип"]
    if not items:
        return HermesQualityCheck(check_name="electrical_standard_recommended", status="passed", message="No normalized items to check.")
    missing = []
    for idx, item in enumerate(items):
        raw_lower = item.raw_name.lower()
        is_cable = any(kw in raw_lower for kw in cable_keywords)
        if is_cable and not item.standard:
            missing.append(f"[{idx}] {item.raw_name}")
    if missing:
        return HermesQualityCheck(
            check_name="electrical_standard_recommended",
            status="warning",
            message=f"Cable items missing ГОСТ/ТУ: {', '.join(missing)}",
        )
    return HermesQualityCheck(check_name="electrical_standard_recommended", status="passed", message="All cable items have ГОСТ/ТУ.")


def check_electrical_nmck_mapping_complete(
    analysis: HermesAnalysisResponse,
    nmck_mapping: NmckMappingResult | None = None,
) -> HermesQualityCheck:
    mapping = nmck_mapping or NmckMappingResult()
    if mapping.mapping_status == "no_nmck_data":
        return HermesQualityCheck(check_name="electrical_nmck_mapping_complete", status="passed", message="No НМЦК data available, skip mapping check.")
    if mapping.mapping_status in ("complete",):
        return HermesQualityCheck(check_name="electrical_nmck_mapping_complete", status="passed", message=f"All {mapping.mapped_count} items mapped to НМЦК.")
    nmck_exists = bool(analysis.summary.nmck)
    if mapping.unmapped_count > 0 and nmck_exists:
        return HermesQualityCheck(
            check_name="electrical_nmck_mapping_complete",
            status="failed",
            message=f"{mapping.unmapped_count} item(s) not mapped to НМЦК despite NMCK={analysis.summary.nmck}.",
        )
    return HermesQualityCheck(
        check_name="electrical_nmck_mapping_complete",
        status="warning" if mapping.unmapped_count > 0 else "passed",
        message=f"{mapping.unmapped_count} unmapped item(s); no NMCK amount to compare.",
    )


CATEGORY_GATE_FUNCTIONS: dict[str, list] = {
    "electrical_goods": [
        check_electrical_required_fields_present,
        check_electrical_quantity_unit_required,
        check_electrical_cable_type_mark_required,
        check_electrical_standard_recommended,
        check_electrical_nmck_mapping_complete,
    ],
}

GATE_FUNCTIONS = [
    check_line_items_required_for_goods,
    check_line_items_required_if_specification_exists,
    check_summary_subject_not_too_generic,
    check_evidence_required_for_high_confidence,
    check_all_documents_used,
]


def run_all_quality_gates(analysis: HermesAnalysisResponse) -> list[HermesQualityCheck]:
    return [fn(analysis) for fn in GATE_FUNCTIONS]


def run_category_quality_gates(
    analysis: HermesAnalysisResponse,
    category: str,
    normalized_items: list[NormalizedLineItem] | None = None,
    nmck_mapping: NmckMappingResult | None = None,
) -> list[HermesQualityCheck]:
    gate_fns = CATEGORY_GATE_FUNCTIONS.get(category, [])
    results: list[HermesQualityCheck] = []
    for fn in gate_fns:
        import inspect
        sig = inspect.signature(fn)
        kwargs: dict[str, Any] = {"analysis": analysis}
        if "normalized_items" in sig.parameters:
            kwargs["normalized_items"] = normalized_items or []
        if "nmck_mapping" in sig.parameters:
            kwargs["nmck_mapping"] = nmck_mapping
        results.append(fn(**kwargs))
    return results


def evidence_coverage_percentage(analysis: HermesAnalysisResponse) -> float:
    total_fields = 0
    covered_fields = 0

    for item in analysis.line_items:
        total_fields += 1
        if item.source_document and item.source_quote:
            covered_fields += 1

    for tr in analysis.technical_requirements:
        total_fields += 1
        if tr.source_document and tr.source_quote:
            covered_fields += 1

    for cr in analysis.certification_requirements:
        total_fields += 1
        if cr.source_document and cr.source_quote:
            covered_fields += 1

    if total_fields == 0:
        return 0.0
    return round((covered_fields / total_fields) * 100, 1)


def determine_final_status(analysis: HermesAnalysisResponse, quality_checks: list[HermesQualityCheck] | None = None) -> tuple[str, str]:
    checks = quality_checks or run_all_quality_gates(analysis)
    failed = [c for c in checks if c.status == "failed"]

    roles_lower = [r.lower() for r in analysis.document_roles]
    has_spec = any("specification" in r or "technical_specification" in r for r in roles_lower)

    if has_spec and not analysis.line_items:
        return ("needs_review", "Specification exists but line_items are empty.")

    is_goods = _has_goods_indicators(analysis)
    if is_goods and not analysis.line_items:
        return ("needs_review", "Goods indicators found but line_items are empty.")

    if analysis.summary.subject and not analysis.line_items:
        subject_lower = analysis.summary.subject.lower().strip()

        if _is_generic_subject(subject_lower):
            return ("needs_review", "Subject is too generic and no line items found.")

    has_extra_docs = any(
        "specification" in d.lower() or "technical_specification" in d.lower()
        or "nmck" in d.lower() or "contract" in d.lower()
        or "тз" in d.lower() or "спецификация" in d.lower()
        or "нмцк" in d.lower() or "контракт" in d.lower()
        for d in analysis.document_roles
    )

    if has_extra_docs and not analysis.line_items:
        return ("needs_review", "Specification/NMCC/contract documents exist but line items are empty.")

    if failed:
        return ("needs_review", f"Quality checks failed: {len(failed)} issue(s).")

    return ("ready", "All quality gates passed.")
