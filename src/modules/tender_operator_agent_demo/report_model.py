"""Canonical procurement report facade with a separate customer projection.

The implementation module preserves the historical canonical contract. This
facade repairs the canonical evidence shape and exposes a sanitized projection
for the R10.1 customer renderer without mutating provider output.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.modules.tender_operator_agent_demo import report_model_legacy as _legacy
from src.modules.tender_operator_agent_demo.decision_core import (
    build_decision_core,
    legacy_bid_decision,
)
from src.modules.tender_operator_agent_demo.document_set_completeness import (
    build_document_set_summary,
)
from src.modules.tender_operator_agent_demo.eis_fact_values import (
    EIS_NOTICE_FACT_TAGS,
    verified_eis_fact_value,
)

for _name, _value in vars(_legacy).items():
    if _name not in {"__name__", "__package__", "__loader__", "__spec__"}:
        globals().setdefault(_name, _value)

UNKNOWN = _legacy.UNKNOWN
CUSTOMER_NOT_EXTRACTED = _legacy.CUSTOMER_NOT_EXTRACTED
_HASH_NAME = _legacy._HASH_NAME
_UUID = re.compile(
    r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_ORIGINAL_BUILD_PROCUREMENT_REPORT_MODEL = _legacy.build_procurement_report_model
_STALE_MISSING_DOCUMENT_MARKERS = (
    "проект контракта не найден",
    "проект контракта отсутств",
    "отсутствует проект контракта",
    "получить проект контракта",
    "запросить отсутствующие документы",
    "отдельное тз",
    "техническое задание или описание объекта закупки не найден",
    "техническое задание отсутств",
)


def _format_source_location(value: Any) -> str:
    if isinstance(value, int) or (
        isinstance(value, str) and value.strip().isdigit()
    ):
        return f"позиция {str(value).strip()}"
    raw = str(value or "").strip()
    row_match = re.search(r"(?:^|:)row:(\d+)(?:$|:)", raw, flags=re.IGNORECASE)
    if row_match:
        return f"позиция {row_match.group(1)}"
    text = re.sub(
        r"[0-9a-f]{64}(?:\.[a-z0-9]+)?",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip(": ")
    if text.isdigit():
        return f"позиция {text}"
    return text if text and not _HASH_NAME.fullmatch(text) else "раздел документа"


def _russian_datetime(value: Any) -> str:
    text = str(value or "").strip()
    if "T" in text:
        parsed = _legacy._parse_timestamp(text)
        if parsed:
            offset = parsed.utcoffset()
            suffix = (
                " (UTC)"
                if offset is not None and offset.total_seconds() == 0
                else ""
            )
            return parsed.strftime("%d.%m.%Y %H:%M") + suffix
    match = re.match(
        r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}:\d{2})"
        r"(?::\d{2}(?:\.\d+)?)?\s*([+-]\d{2}:\d{2})?",
        text,
    )
    if not match:
        return text or UNKNOWN
    zone = {
        "+12:00": " (UTC+12)",
        "+03:00": " (UTC+3)",
        "+00:00": " (UTC)",
    }.get(match.group(5), "")
    return (
        f"{match.group(1)}.{match.group(2)}.{match.group(3)} "
        f"{match.group(4)}{zone}"
    )


_legacy._format_source_location = _format_source_location
_legacy._russian_datetime = _russian_datetime


def _canonical_evidence_map(model: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for row in model.get("line_items", []):
        if not isinstance(row, dict):
            continue
        for evidence_id in row.get("evidence_ids", []):
            evidence.append(
                {
                    "evidence_id": evidence_id,
                    "document": row.get("source_document_id"),
                    "row": row.get("source_row"),
                    "short_excerpt": row.get("original_name"),
                    "related_items": [row.get("stable_item_id")],
                }
            )
    for risk_index, risk in enumerate(model.get("risks", []), start=1):
        if not isinstance(risk, dict):
            continue
        for locator_index, locator in enumerate(
            risk.get("evidence_locators", []), start=1
        ):
            if (
                not isinstance(locator, dict)
                or not locator.get("document")
                or not locator.get("locator")
            ):
                continue
            evidence.append(
                {
                    "evidence_id": f"risk:{risk_index}:locator:{locator_index}",
                    "document": locator["document"],
                    "row": locator["locator"],
                    "short_excerpt": risk.get("risk")
                    or risk.get("description")
                    or "Подтверждённый риск",
                    "related_items": [],
                }
            )
    return evidence


def _document_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    current = metadata.get("document_set_summary")
    if isinstance(current, dict) and current.get("logical_documents") is not None:
        return dict(current)
    files = [item for item in metadata.get("files", []) if isinstance(item, dict)]
    return build_document_set_summary(files)


def _is_stale_missing_document_text(value: Any) -> bool:
    lowered = str(value or "").lower()
    return any(marker in lowered for marker in _STALE_MISSING_DOCUMENT_MARKERS)


def _safe_customer_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or _HASH_NAME.fullmatch(text) or _UUID.fullmatch(text):
        return None
    if text.startswith(("/", "file:")) or "/Users/" in text or "/Volumes/" in text:
        return None
    return text


def _clean_complete_document_model(
    model: dict[str, Any], document_summary: dict[str, Any]
) -> None:
    """Remove notice-only conclusions when the canonical set is complete."""

    if document_summary.get("status") != "complete":
        return
    decision = model.get("customer_decision")
    if isinstance(decision, dict):
        reasons = [
            item
            for item in decision.get("reasons", [])
            if not _is_stale_missing_document_text(item)
        ]
        complete_reason = (
            "Техническая документация и проект контракта включены в комплект анализа."
        )
        if complete_reason not in reasons:
            reasons.append(complete_reason)
        decision["reasons"] = reasons
        next_actions = [
            item
            for item in model.get("action_plan", [])
            if item and not _is_stale_missing_document_text(item)
        ]
        decision["next_action"] = (
            next_actions[0]
            if next_actions
            else "Проверить коммерческие предложения и собственную себестоимость до решения об участии."
        )
    for key in ("corpus_limitations", "limitations"):
        if isinstance(model.get(key), list):
            model[key] = [
                item
                for item in model[key]
                if not _is_stale_missing_document_text(item)
            ]
    if isinstance(model.get("missing_data"), list):
        model["missing_data"] = [
            item
            for item in model["missing_data"]
            if not _is_stale_missing_document_text(
                item.get("description") if isinstance(item, dict) else item
            )
        ]
    if isinstance(model.get("customer_questions"), list):
        model["customer_questions"] = [
            item
            for item in model["customer_questions"]
            if not _is_stale_missing_document_text(
                item.get("question") if isinstance(item, dict) else item
            )
        ]
    bid = model.get("bid_decision")
    if isinstance(bid, dict):
        for key in ("blockers", "conditions", "rationale"):
            if isinstance(bid.get(key), list):
                bid[key] = [
                    item
                    for item in bid[key]
                    if not _is_stale_missing_document_text(item)
                ]
    coverage = model.get("document_coverage")
    if isinstance(coverage, dict):
        coverage["missing"] = []
        if coverage.get("impact") == "Договорный анализ ограничен":
            coverage["impact"] = ""
    contract = model.get("contract_conditions")
    if isinstance(contract, dict):
        contract["status"] = "present"
        contract["reason"] = "Проект контракта включён в комплект анализа."


def _ground_customer_decision_claims(model: dict[str, Any]) -> None:
    """Replace legacy blanket confirmations with evidence-bound statements."""

    customer_decision = model.get("customer_decision")
    if not isinstance(customer_decision, dict):
        customer_decision = {}
        model["customer_decision"] = customer_decision

    core = model.get("decision_core")
    facts = core.get("facts") if isinstance(core, dict) else {}
    facts = facts if isinstance(facts, dict) else {}
    confirmed: list[str] = []

    labels = {
        "procurement_title": "предмет закупки",
        "application_deadline": "срок подачи заявок",
        "nmck": "НМЦК",
    }
    for key, label in labels.items():
        fact = facts.get(key)
        if (
            isinstance(fact, dict)
            and fact.get("status") == "KNOWN"
            and fact.get("evidence")
        ):
            confirmed.append(label)

    field_evidence = model.get("field_evidence")
    field_evidence = field_evidence if isinstance(field_evidence, dict) else {}
    customer_name = str(model.get("customer_name") or "").strip()
    if (
        field_evidence.get("customer_name")
        and customer_name
        and customer_name != "Заказчик не извлечён"
    ):
        confirmed.append("заказчик")

    line_items = [row for row in (model.get("line_items") or []) if isinstance(row, dict)]
    bound_items = [
        row
        for row in line_items
        if row.get("evidence_ids") and row.get("field_provenance", {}).get("name")
    ]
    if line_items and len(bound_items) == len(line_items):
        confirmed.append("извлечённые позиции закупки")

    fully_quantified = bool(line_items) and all(
        row.get("quantity_status") == "specified"
        and row.get("quantity") not in (None, "")
        and row.get("field_provenance", {}).get("quantity")
        and row.get("field_provenance", {}).get("unit")
        for row in line_items
    )
    if fully_quantified:
        confirmed.append("количество и единица измерения по всем извлечённым позициям")

    existing_not_evaluated = [
        str(item)
        for item in (customer_decision.get("not_evaluated") or [])
        if str(item).strip()
    ]
    if line_items and not fully_quantified:
        existing_not_evaluated.append(
            "количество и/или единица измерения не подтверждены для всех извлечённых позиций"
        )
    if not line_items:
        existing_not_evaluated.append(
            "позиции и количество не извлечены в source-bound виде"
        )
    contract_status = str(model.get("contract_draft_status") or "").strip().lower()
    if contract_status == "absent":
        existing_not_evaluated.append(
            "договорные условия не оценены: проект контракта не подтверждён в комплекте"
        )
    elif contract_status == "parse_failed":
        existing_not_evaluated.append(
            "договорные условия не оценены: проект контракта присутствует, но его текст не извлечён полностью"
        )

    def dedupe(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result

    customer_decision["confirmed"] = dedupe(confirmed)
    customer_decision["not_evaluated"] = dedupe(existing_not_evaluated)

    reasons: list[str] = []
    if confirmed:
        reasons.append("Source-bound подтверждение: " + ", ".join(confirmed) + ".")
    else:
        reasons.append(
            "Нет набора source-bound фактов, достаточного для положительного утверждения о реквизитах или объёме."
        )

    if model.get("contract_draft_status") == "absent":
        reasons.append("Проект контракта не найден в предоставленном комплекте.")
    elif model.get("contract_draft_status") == "parse_failed":
        reasons.append("Проект контракта присутствует, но его текст не извлечён полностью.")

    customer_documents = model.get("customer_documents") or []
    has_technical_document = any(
        isinstance(item, dict) and item.get("type") == "технический документ"
        for item in customer_documents
    )
    if not has_technical_document:
        reasons.append("Отдельное ТЗ или описание объекта закупки не найдено.")
    customer_decision["reasons"] = reasons


def _reconcile_contract_presence_from_document_summary(
    model: dict[str, Any], document_summary: dict[str, Any]
) -> None:
    """Distinguish a missing contract from a present-but-unparsed contract."""

    logical_documents = [
        item
        for item in (document_summary.get("logical_documents") or [])
        if isinstance(item, dict)
    ]
    contract_documents = [
        item
        for item in logical_documents
        if item.get("kind") == "contract_draft"
        or "проект контракта" in str(item.get("type") or "").lower()
        or "проект контракта" in str(item.get("name") or "").lower()
    ]
    if not contract_documents:
        return

    names = [
        str(item.get("name") or "Проект контракта")
        for item in contract_documents
    ]
    evidence_ids = [
        f"document_set:contract_draft:{index}"
        for index, _item in enumerate(contract_documents, start=1)
    ]
    current_status = str(model.get("contract_draft_status") or "").strip().lower()

    model["contract_draft_documents"] = names
    model["contract_draft_evidence_ids"] = evidence_ids

    if current_status != "present":
        model["contract_draft_status"] = "parse_failed"
        contract = model.get("contract_conditions")
        if not isinstance(contract, dict):
            contract = {}
            model["contract_conditions"] = contract
        contract["status"] = "parse_failed"
        contract["reason"] = (
            "Проект контракта присутствует в комплекте, но его текст не извлечён полностью."
        )


def _align_customer_decision_with_decision_core(model: dict[str, Any]) -> None:
    """Prevent the legacy customer verdict from overstating Decision Core readiness."""

    raw_core = model.get("decision_core")
    if not isinstance(raw_core, dict):
        return
    core_decision = (
        raw_core.get("decision")
        if isinstance(raw_core.get("decision"), dict)
        else {}
    )
    status = str(core_decision.get("status") or "").strip().upper()
    customer_decision = model.get("customer_decision")
    if not isinstance(customer_decision, dict):
        customer_decision = {}
        model["customer_decision"] = customer_decision

    next_action = core_decision.get("next_action")
    rationale = list(core_decision.get("rationale") or [])
    if status == "NEEDS_REVIEW":
        customer_decision["recommendation"] = "Требуется проверка"
        customer_decision["reasons"] = rationale
        if next_action:
            customer_decision["next_action"] = next_action
        model["decision"] = "Требуется ручная проверка перед коммерческим расчётом"
    elif status == "NO_GO":
        customer_decision["recommendation"] = "Не участвовать"
        customer_decision["reasons"] = rationale
        if next_action:
            customer_decision["next_action"] = next_action
        model["decision"] = "Не участвовать: подтверждён жёсткий блокер"


def build_procurement_report_model(
    metadata: dict[str, Any],
    outputs: dict[str, dict[str, Any]],
    *,
    repository_sha: str = "unknown",
) -> dict[str, Any]:
    model = _ORIGINAL_BUILD_PROCUREMENT_REPORT_MODEL(
        metadata,
        outputs,
        repository_sha=repository_sha,
    )
    # The legacy report builder may prefer an arbitrary document heading to the
    # genuine EIS subject. Restore only a registry-verified getDocsIP XML fact.
    source_refs = metadata.get("_field_evidence")
    source_refs = source_refs if isinstance(source_refs, dict) else {}
    if (
        metadata.get("procurement_source") == "zakupki_gov_ru_getdocs_ip"
        and source_refs.get("procurement_title") == "eis_notice:procurement_subject"
    ):
        xml_subject = str(metadata.get("procurement_title") or "").strip()
        if xml_subject:
            model["procurement_title"] = xml_subject
            refs = dict(model.get("field_evidence") or {})
            refs["procurement_title"] = "eis_notice:procurement_subject"
            model["field_evidence"] = refs
            proof = metadata.get("_verified_notice_facts")
            if isinstance(proof, dict):
                model["_verified_notice_facts"] = dict(proof)
    analysis_as_of = (
        metadata.get("analysis_completed_at")
        or metadata.get("prepared_at")
        or metadata.get("created_at")
    )
    parsed_as_of = _legacy._parse_timestamp(analysis_as_of)
    model["analysis_as_of"] = _russian_datetime(analysis_as_of)
    model["analysis_as_of_iso"] = (
        parsed_as_of.isoformat() if parsed_as_of else None
    )
    model["publication_datetime_display"] = _russian_datetime(
        model.get("publication_datetime")
    )
    model["application_deadline_display"] = _russian_datetime(
        model.get("application_deadline")
    )
    model["evidence_map"] = _canonical_evidence_map(model)
    document_summary = _document_summary(metadata)
    model_metadata = dict(model.get("metadata") or {})
    model_metadata.update(
        {
            "document_set_summary": document_summary,
            "document_count": document_summary.get("physical_file_count", 0),
            "logical_document_count": document_summary.get(
                "logical_document_count", 0
            ),
            "document_set_status": document_summary.get("status", "unknown"),
        }
    )
    procurement_law = metadata.get("procurement_law") or metadata.get("procurement_regime")
    if procurement_law:
        model["procurement_law"] = procurement_law
    model["metadata"] = model_metadata
    _clean_complete_document_model(model, document_summary)
    _reconcile_contract_presence_from_document_summary(model, document_summary)
    analysis_context = (
        outputs.get("requirements", {}).get("analysis_context", {})
        if isinstance(outputs.get("requirements"), dict)
        else {}
    )
    supplier_profile = (
        analysis_context.get("supplier_profile")
        if isinstance(analysis_context, dict)
        else None
    )
    model["decision_core"] = build_decision_core(
        model,
        supplier_profile=supplier_profile,
    )
    model["bid_decision"] = legacy_bid_decision(model["decision_core"])
    _ground_customer_decision_claims(model)
    _align_customer_decision_with_decision_core(model)
    return model


def _customer_document_label(value: Any) -> tuple[str, str]:
    text = _safe_customer_text(value)
    if not text:
        return "Документы закупки", "подтверждающий документ"
    if Path(text).name != text:
        return "Документы закупки", "подтверждающий документ"
    lowered = text.lower()
    role = "notice" if "notice" in lowered or "извещ" in lowered else ""
    return _legacy._customer_document_label(
        {"display_name": text, "role_hint": role}
    )


def _customer_evidence_location(value: Any) -> str:
    location = _format_source_location(value)
    if location.startswith("раздел "):
        return location
    if location.startswith("позиция "):
        return f"раздел «Объект закупки», {location}"
    return location



def _customer_decision_evidence(values: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in values or []:
        if not isinstance(item, dict):
            continue
        document_label, _document_type = _customer_document_label(item.get("document"))
        location = _customer_evidence_location(item.get("locator"))
        key = (document_label, location)
        if key in seen:
            continue
        seen.add(key)
        result.append({"document_label": document_label, "location": location})
    return result


def _verified_notice_fact_projection(model: dict[str, Any]) -> dict[str, Any]:
    """Only registry-matched original XML values become customer-visible KNOWN."""
    proof = model.get("_verified_notice_facts")
    proof = proof if isinstance(proof, dict) else {}
    file_id = str(proof.get("file_id") or "")
    document = str(proof.get("document") or "")
    registry = str(proof.get("registry_number") or "")
    valid = (
        bool(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", file_id))
        and bool(document)
        and Path(document).name == document
        and "\\" not in document
        and bool(re.fullmatch(r"[0-9]{19}", registry))
        and registry == str(model.get("procurement_number") or "")
    )
    originals = proof.get("values")
    originals = originals if isinstance(originals, dict) else {}
    facts: dict[str, Any] = {}
    for field, tag in EIS_NOTICE_FACT_TAGS:
        excerpt = originals.get(field) if valid else None
        value = verified_eis_fact_value(field, excerpt)
        if value is not None:
            facts[field] = {
                "status": "KNOWN",
                "value": excerpt,
                "evidence": [{
                    "source_ref": f"eis-xml:{file_id}:{tag}",
                    "document": document,
                    "locator": f"XML:{tag}",
                    "excerpt": excerpt,
                    "file_id": file_id,
                }],
            }
        else:
            facts[field] = {"status": "UNKNOWN", "value": None, "evidence": []}
    return facts


def _customer_decision_core_projection(model: dict[str, Any]) -> dict[str, Any] | None:
    raw = model.get("decision_core")
    if not isinstance(raw, dict):
        return None
    decision = raw.get("decision") if isinstance(raw.get("decision"), dict) else {}
    blockers = []
    for item in raw.get("blockers", []) or []:
        if not isinstance(item, dict):
            continue
        blockers.append(
            {
                "code": item.get("code"),
                "summary": item.get("summary"),
                "hard": bool(item.get("hard")),
                "evidence": _customer_decision_evidence(item.get("evidence")),
            }
        )
    readiness = []
    for item in raw.get("readiness", []) or []:
        if not isinstance(item, dict):
            continue
        readiness.append(
            {
                "code": item.get("code"),
                "label": item.get("label"),
                "status": item.get("status"),
                "required": bool(item.get("required")),
                "blocking": bool(item.get("blocking")),
                "summary": item.get("summary"),
                "evidence": _customer_decision_evidence(item.get("evidence")),
            }
        )
    return {
        "contract_version": raw.get("contract_version"),
        "procurement_regime": raw.get("procurement_regime"),
        "facts": _verified_notice_fact_projection(model),
        "decision": {
            "status": decision.get("status"),
            "confidence": decision.get("confidence"),
            "rationale": list(decision.get("rationale") or []),
            "next_action": decision.get("next_action"),
            "evidence": _customer_decision_evidence(decision.get("evidence")),
            "human_control_required": bool(decision.get("human_control_required", True)),
            "external_action_allowed": bool(decision.get("external_action_allowed", False)),
        },
        "blockers": blockers,
        "readiness": readiness,
        "unknowns": [
            dict(item)
            for item in raw.get("unknowns", []) or []
            if isinstance(item, dict)
        ],
        "supplier_profile_bound": bool(raw.get("supplier_profile_bound")),
        "safety": dict(raw.get("safety") or {}),
    }



def _customer_commercial_core_projection(model: dict[str, Any]) -> dict[str, Any] | None:
    raw = model.get("commercial_core")
    if not isinstance(raw, dict):
        return None
    catalog = raw.get("catalog") if isinstance(raw.get("catalog"), dict) else {}
    matches = []
    for item in raw.get("matches", []) or []:
        if not isinstance(item, dict):
            continue
        evidence = []
        for ref in item.get("evidence", []) or []:
            if not isinstance(ref, dict):
                continue
            evidence.append(
                {
                    "source_file": Path(str(ref.get("source_file") or "Каталог")).name,
                    "sheet": str(ref.get("sheet") or ""),
                    "row": ref.get("row"),
                }
            )
        matches.append(
            {
                "tender_name": item.get("tender_name"),
                "tender_quantity": item.get("tender_quantity"),
                "tender_unit": item.get("tender_unit"),
                "status": item.get("status"),
                "catalog_title": item.get("catalog_title"),
                "catalog_unit": item.get("catalog_unit"),
                "catalog_unit_price": item.get("catalog_unit_price"),
                "currency": item.get("currency"),
                "match_score": item.get("match_score"),
                "rationale": list(item.get("rationale") or []),
                "evidence": evidence,
            }
        )
    return {
        "contract_version": raw.get("contract_version"),
        "catalog": {
            "status": catalog.get("status"),
            "source_file": Path(str(catalog.get("source_file") or "Каталог")).name,
            "warnings": list(catalog.get("warnings") or []),
            "unknowns": list(catalog.get("unknowns") or []),
            "rows_count": len(catalog.get("rows") or []),
        },
        "matches": matches,
        "coverage": dict(raw.get("coverage") or {}),
        "economics": dict(raw.get("economics") or {}),
        "feasibility_status": raw.get("feasibility_status"),
        "rationale": list(raw.get("rationale") or []),
        "next_action": raw.get("next_action"),
        "human_control_required": bool(raw.get("human_control_required", True)),
        "external_action_allowed": bool(raw.get("external_action_allowed", False)),
        "safety": dict(raw.get("safety") or {}),
    }


def build_customer_report_projection(model: dict[str, Any]) -> dict[str, Any]:
    """Return a sanitized customer model without mutating canonical data."""

    metadata = (
        model.get("metadata")
        if isinstance(model.get("metadata"), dict)
        else {}
    )
    document_summary = (
        metadata.get("document_set_summary")
        if isinstance(metadata.get("document_set_summary"), dict)
        else {}
    )
    logical_documents = document_summary.get("logical_documents")
    source_documents = (
        logical_documents
        if isinstance(logical_documents, list) and logical_documents
        else model.get("customer_documents", [])
    )
    documents = [
        {
            "name": str(item.get("name") or "Документ закупки"),
            "type": str(item.get("type") or "документ"),
        }
        for item in source_documents
        if isinstance(item, dict)
    ]

    raw_line_items = [
        row for row in model.get("line_items", []) if isinstance(row, dict)
    ]
    okpd2_codes = [
        item
        for item in model.get("okpd2_codes", [])
        if isinstance(item, dict) and _safe_customer_text(item.get("code"))
    ]
    single_item_okpd2 = (
        str(okpd2_codes[0]["code"])
        if len(raw_line_items) == 1 and len(okpd2_codes) == 1
        else None
    )
    line_items: list[dict[str, Any]] = []
    for row in raw_line_items:
        location = _customer_evidence_location(row.get("source_row"))
        source_display = "Извещение о закупке — " + location
        characteristics = [
            text
            for value in row.get("characteristics", [])
            if (text := _safe_customer_text(value))
        ]
        line_items.append(
            {
                "sequence": row.get("sequence"),
                "original_name": row.get("original_name")
                or row.get("display_name")
                or UNKNOWN,
                "quantity_display": row.get("quantity_display") or UNKNOWN,
                "unit_original": row.get("unit_original") or UNKNOWN,
                "okpd2": row.get("okpd2") or single_item_okpd2,
                "characteristics": characteristics,
                "source_display": source_display,
            }
        )

    customer_evidence: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in model.get("evidence_map", []):
        if not isinstance(item, dict):
            continue
        document_label, document_type = _customer_document_label(
            item.get("document")
        )
        location = _customer_evidence_location(item.get("row"))
        key = (document_label, document_type, location)
        if key in seen:
            continue
        seen.add(key)
        customer_evidence.append(
            {
                "document_label": document_label,
                "document_type": document_type,
                "location": location,
            }
        )

    return {
        "procurement_number": model.get("procurement_number"),
        "procurement_title": model.get("procurement_title"),
        "procurement_regime": (model.get("decision_core") or {}).get("procurement_regime") if isinstance(model.get("decision_core"), dict) else "unknown",
        "customer_name": model.get("customer_name"),
        "publication_datetime_display": model.get(
            "publication_datetime_display"
        )
        or _russian_datetime(model.get("publication_datetime")),
        "application_deadline_display": model.get(
            "application_deadline_display"
        )
        or _russian_datetime(model.get("application_deadline")),
        "analysis_as_of": model.get("analysis_as_of"),
        "analysis_as_of_iso": model.get("analysis_as_of_iso"),
        "deadline_status": model.get("deadline_status"),
        "nmck": model.get("nmck"),
        "delivery_place": model.get("delivery_place"),
        "document_set_status": document_summary.get("status") or "unknown",
        "missing_required_document_kinds": list(
            document_summary.get("missing_required_document_kinds") or []
        ),
        "documents_count": int(
            document_summary.get("logical_document_count") or len(documents)
        ),
        "physical_files_count": int(
            document_summary.get("physical_file_count")
            or metadata.get("document_count")
            or len(documents)
        ),
        "document_set_complete": document_summary.get("status") == "complete",
        "customer_documents": documents,
        "customer_decision": dict(model.get("customer_decision") or {}),
        "decision_core": _customer_decision_core_projection(model),
        "commercial_core": _customer_commercial_core_projection(model),
        "line_items": line_items,
        "evidence_map": customer_evidence,
        "unit_economics": (
            dict(model.get("unit_economics") or {})
            if model.get("unit_economics")
            else None
        ),
        "corpus_limitations": list(model.get("corpus_limitations") or []),
        "customer_questions": list(model.get("customer_questions") or []),
        "risks": [
            dict(item)
            for item in model.get("risks", [])
            if isinstance(item, dict)
        ],
    }
