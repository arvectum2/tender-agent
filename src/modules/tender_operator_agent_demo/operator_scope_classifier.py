"""Evidence-bound product procurement scope classification.

Signals retain document name, role, source file ID and line locator. No
resource fetching, inference network calls or automatic GO/NO-GO decisions.
"""

from __future__ import annotations

import re
from typing import Any

from src.modules.procurement_analysis.frozen_types import AnalyzedDocument
from src.modules.tender_operator_agent_demo.goods_source_facts import (
    semantic_procurement_role,
)
from src.modules.tender_operator_agent_demo.procurement_kind_classifier import (
    infer_procurement_kind as _infer_procurement_kind,
)


def _is_generic_procurement_scope_boilerplate(text: str) -> bool:
    normalized = " ".join((text or "").lower().replace("ё", "е").split())
    if not normalized:
        return False
    has_goods = bool(re.search(r"\bпоставк\w*\s+товар", normalized))
    has_works = bool(re.search(r"\bвыполнени[ея]\s+работ", normalized))
    has_services = bool(re.search(r"\bоказани[ея]\s+услуг", normalized))
    return has_goods and has_works and has_services


_SCOPE_SIGNALS: tuple[tuple[str, str, int, str], ...] = (
    ("rental", r"\bарендодатель\w*(?:\s+обяз\w*)?\s+предостав\w*.*\bвременн\w*(?:\s+\w+){0,3}\s+пользован", 6, "rental_temporary_use"),
    ("rental", r"\bарендн\w*\s+плат", 5, "rental_payment"),
    ("rental", r"\bсрок\s+аренд", 4, "rental_term"),
    ("rental", r"\bаренд\w*", 2, "rental_marker"),
    ("services", r"\bисполнитель\w*\s+обяз\w*\s+оказ", 5, "performer_services"),
    ("services", r"\bоказани[ея]\s+услуг", 5, "services_subject"),
    ("services", r"\bпредмет\w*.{0,80}\bоказан\w*\s+услуг", 5, "services_contract_subject"),
    ("services", r"\bуслуг\w*", 1, "services_supporting_marker"),
    ("goods", r"\bпоставщик\w*\s+обяз\w*\s+постав", 5, "supplier_delivery"),
    ("goods", r"\bпоставка\s+товар", 4, "goods_delivery_subject"),
    ("goods", r"\b(?:количество|место|срок)\s+поставки\s+товар", 4, "goods_delivery_term"),
    ("goods", r"\bпоставк\w*\s+товар", 3, "goods_supply_marker"),
    ("goods", r"\bпоставк\w*\s+[^\n]{3,100}", 3, "goods_supply_subject"),
    ("works", r"\bподрядчик\w*\s+обяз\w*\s+выполн", 5, "contractor_works"),
    ("works", r"\bвыполнени[ея]\s+работ", 5, "works_subject"),
    ("works", r"\bрезультат\w*\s+работ", 4, "works_result"),
    ("works", r"\bакт\s+выполненн\w*\s+работ", 4, "works_acceptance"),
)


def _scope_signal_evidence(metadata: dict[str, Any], documents: list[AnalyzedDocument], notice_text: str) -> list[dict[str, Any]]:
    sources: list[tuple[str, str, str, str, str]] = []
    title = str(metadata.get("tender_title") or "")
    if title:
        sources.append(("metadata:tender_title", "METADATA", "metadata:tender_title", title, "METADATA"))
    if notice_text and notice_text != title:
        sources.append(("notice", "NOTICE", "notice", notice_text, "NOTICE"))
    declared_roles = {
        "notice": "NOTICE",
        "technical_spec": "TECHNICAL_SPEC",
        "contract_draft": "CONTRACT_DRAFT",
        "specification_table": "SPECIFICATION_TABLE",
        "supporting": "SUPPORTING",
    }
    for document in documents:
        # The ingestion role is more reliable than lexical role detection for a
        # contract that happens to contain an NMCK or boilerplate reference.
        semantic_role = declared_roles.get(str(getattr(document, "role", "")).lower()) or semantic_procurement_role(document)
        for row, raw_line in enumerate((document.text or "").splitlines(), start=1):
            line = " ".join(raw_line.split())
            if line and not _is_generic_procurement_scope_boilerplate(line):
                sources.append((document.display_name, document.file_id, f"line:{row}", line, semantic_role))

    evidence: list[dict[str, Any]] = []
    for source_document, file_id, locator, text, semantic_role in sources:
        for category, pattern, weight, basis in _SCOPE_SIGNALS:
            if re.search(pattern, text, re.IGNORECASE):
                evidence.append({
                    "category": category,
                    "weight": weight,
                    "basis": basis,
                    "source_document": source_document,
                    "file_id": file_id,
                    "locator": locator,
                    "excerpt": text[:500],
                    "semantic_role": semantic_role,
                })
    return evidence


def _classify_procurement_scope(metadata: dict[str, Any], documents: list[AnalyzedDocument], notice_text: str) -> dict[str, Any]:
    """Classify the procurement subject from weighted, source-backed signals."""
    title = str(metadata.get("tender_title") or "").lower()
    text = "\n".join([title, notice_text, *[(doc.text or "") for doc in documents]]).lower()
    evidence = _scope_signal_evidence(metadata, documents, notice_text)
    # Repeated boilerplate must not win solely through line count.  A category
    # receives at most one strongest contribution per document;
    # technical specifications and contract drafts are the most probative roles.
    role_multiplier = {"CONTRACT_DRAFT": 2, "TECHNICAL_SPEC": 2, "SPECIFICATION_TABLE": 2, "NOTICE": 2}
    best_document_signal: dict[tuple[str, str], dict[str, Any]] = {}
    for item in evidence:
        key = (item["category"], item["file_id"])
        if item["weight"] > best_document_signal.get(key, {"weight": -1})["weight"]:
            best_document_signal[key] = item
    scores = {category: 0 for category in ("goods", "services", "works", "rental")}
    for item in best_document_signal.values():
        scores[item["category"]] += item["weight"] * role_multiplier.get(item["semantic_role"], 1)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    primary, top_score = ranked[0]
    second_score = ranked[1][1]
    strong_categories = [category for category, score in ranked if score >= 4]
    if top_score < 3:
        primary = "unresolved"
        decision_basis = "No category has sufficient independent strong evidence."
    elif len(strong_categories) >= 2 and second_score >= top_score - 1:
        primary = "mixed"
        decision_basis = "Independent strong evidence supports competing procurement subjects."
    else:
        decision_basis = "Highest weighted procurement-subject evidence is unambiguous."
    structured_codes = (metadata.get("procurement") or {}).get("okpd2_codes", [])
    service_okpd = any(
        str(code.get("code", "")).startswith("62.02")
        for code in structured_codes if isinstance(code, dict)
    )
    okpd_works = any(str(code.get("code", "")).startswith(("41.", "42.", "43.")) for code in structured_codes if isinstance(code, dict))
    strong_works = okpd_works or any(marker in text for marker in ("смета", "кс-2", "кс-3", "ведомость объемов работ"))
    has_services = scores["services"] > 0
    title_kind = _infer_procurement_kind(title)
    inferred_kind = _infer_procurement_kind(text)
    # A titled supply or a detailed structured product list is authoritative;
    # installation/adjustment in contract boilerplate only makes it mixed.
    software_kinds = {"mixed", "software_modification", "integration", "license", "software_support"}
    support_certificate = (
        "код активации" in text and "техническ" in text and "поддержк" in text
        and any(marker in text for marker in ("средств защиты информации", "программ", "лиценз"))
    )
    if service_okpd or support_certificate:
        primary = "services"
        decision_basis = "Structured service evidence overrides unstructured text signals."
    elif title_kind in software_kinds:
        primary = title_kind
    elif inferred_kind in software_kinds and scores["goods"] == 0:
        primary = inferred_kind
    elif strong_works and primary == "unresolved":
        primary = "works"
    applicable = primary == "goods"
    return {
        "procurement_primary_scope": primary,
        "contains_goods": scores["goods"] > 0,
        "contains_works": strong_works,
        "contains_services": has_services,
        "contains_rental": scores["rental"] > 0,
        "scope_scores": scores,
        "classification_evidence": evidence,
        "scope_decision_basis": decision_basis,
        "software_service_support": service_okpd or support_certificate,
        "activation_support_item": "код активации" in text and "техническ" in text and "поддержк" in text,
        "goods_extraction_applicable": applicable,
        "scope_classification_conflict": primary in {"mixed", "unresolved"},
    }
