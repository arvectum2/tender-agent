"""Source-first report projection of tender requirements and procurement context.

Only an orchestration-free projection. Authoritative claims, source precedence,
field evidence and UNKNOWN/default guards come from explicit existing inputs.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_operator_requirements_context(
    *,
    requirement_rows: list[dict[str, Any]],
    preliminary_analysis: dict[str, Any],
    metadata: dict[str, Any],
    documents: list[Any],
    contract_documents: list[Any],
    contract_draft_status: str,
    contract_draft_text: str,
    notice_text: str,
    scope: dict[str, Any],
    procurement_kind: str,
    goods_positions: list[Any],
    output_warnings: list[str],
    contract_term_facts: dict[str, Any],
    contract_term_conflicts: list[Any],
    economics: dict[str, Any] | None,
    delivery_address_from_preliminary: Callable[..., str | None],
    _service_okpd2_from_sources: Callable[..., str | None],
    _extract_notice_price: Callable[..., Any],
) -> dict[str, Any]:
    return {
        "requirements": requirement_rows,
        "preliminary_analysis": preliminary_analysis,
        "analysis_context": {
            "procurement_number": metadata.get("procurement_id"),
            "procurement_subject": (preliminary_analysis.get("overview") or [metadata.get("tender_title")])[0].removeprefix("Предмет закупки: "),
            "customer_name": metadata.get("customer_name") or (metadata.get("procurement") or {}).get("customer_name"),
            "customer_inn": metadata.get("customer_inn") or (metadata.get("procurement") or {}).get("customer_inn"),
            "customer_kpp": metadata.get("customer_kpp") or (metadata.get("procurement") or {}).get("customer_kpp"),
            "delivery_place": metadata.get("delivery_place") or delivery_address_from_preliminary(preliminary_analysis),
            "delivery_address": metadata.get("delivery_address") or delivery_address_from_preliminary(preliminary_analysis),
            "delivery_region": metadata.get("delivery_region"),
            "delivery_status": metadata.get("delivery_status") or ("known" if delivery_address_from_preliminary(preliminary_analysis) else "unknown"),
            "delivery_evidence_ids": [metadata.get("_field_evidence", {}).get("delivery_place")] if metadata.get("_field_evidence", {}).get("delivery_place") else [],
            "contract_draft_status": contract_draft_status,
            "contract_draft_documents": [doc.display_name for doc in contract_documents],
            "contract_draft_evidence_ids": [f"contract:{doc.file_id}" for doc in contract_documents],
            "procurement_scope": scope,
            "goods_extraction_applicable": scope["goods_extraction_applicable"],
            "scope_classification_conflict": scope["scope_classification_conflict"],
            "procurement_category": procurement_kind,
            "domain": preliminary_analysis.get("domain_profile", "unknown"),
            "law": metadata.get("law"),
            "okpd2": _service_okpd2_from_sources(notice_text, documents) if procurement_kind == "services" else None,
            "okpd2_codes": metadata.get("okpd2_codes") or (metadata.get("procurement") or {}).get("okpd2_codes", []),
            "nmck": _extract_notice_price(metadata, notice_text, contract_draft_text),
            "positions": goods_positions,
            "currency": "RUB",
            "service_items": preliminary_analysis.get("service_items", []),
            "document_inventory": [doc.display_name for doc in documents],
            "document_coverage": "partial" if procurement_kind == "services" and not contract_draft_text else "available",
            "missing_documents": [] if contract_draft_status in {"present", "parse_failed"} else preliminary_analysis.get("missing_documents", []),
            "extraction_warnings": output_warnings,
            "known_contract_terms": preliminary_analysis.get("contract_highlights", []) if contract_draft_text else [],
            "unknown_contract_terms": (["payment", "acceptance", "penalties", "security", "liability"] if not contract_draft_text else []),
            "contract_term_facts": [fact.as_dict() for fact in contract_term_facts.values()],
            "contract_term_conflicts": contract_term_conflicts,
            **{field: fact.value for field, fact in contract_term_facts.items()},
            "supplier_profile": None,
            "commercial_inputs": economics or {},
            "evidence_map": [item.get("evidence_ids", []) for item in preliminary_analysis.get("service_items", [])],
        },
        "manual_review_points": [
            "Проверить корректность распределения документов по ролям.",
            "Подтвердить ключевые требования по исходным документам перед внешними действиями.",
        ],
    }
