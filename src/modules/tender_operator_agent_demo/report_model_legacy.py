"""Canonical, renderer-neutral procurement report model.

All customer-facing formats must consume this model.  It deliberately keeps
unknown values explicit and never calculates a total from unit prices.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from src.shared.config.settings import get_settings

UNKNOWN = "Данных недостаточно — требуется проверка"
CUSTOMER_NOT_EXTRACTED = "Заказчик не извлечён"
_HASH_NAME = re.compile(r"^[0-9a-f]{64}(?:\.[a-z0-9]+)?$", re.IGNORECASE)


def _customer_display_name(value: Any) -> str:
    """Keep internal tenant/customer identifiers out of customer reports."""
    if value is None or not str(value).strip():
        return CUSTOMER_NOT_EXTRACTED
    text = str(value).strip()
    if re.fullmatch(r"(?:cus|customer|tenant)[-_][a-z0-9_-]+", text, flags=re.IGNORECASE):
        return CUSTOMER_NOT_EXTRACTED
    return text


def _customer_document_label(item: dict[str, Any]) -> tuple[str, str]:
    """Return a public document label without exposing storage identifiers."""
    name = str(item.get("display_name") or item.get("original_name") or item.get("stored_name") or "")
    role = str(item.get("role_hint") or item.get("document_kind") or "").lower()
    lowered = name.lower()
    if role == "contract_draft" or "contract" in lowered or "контракт" in lowered:
        return "Проект контракта", "проект контракта"
    if role in {"technical_spec", "technical_specification", "procurement_object_description"} or any(value in lowered for value in ("тз", "spec", "описан")):
        return "Техническое задание / описание объекта закупки", "технический документ"
    if "protocol" in lowered or "протокол" in lowered:
        return "Протокол закупочной процедуры", "протокол"
    if "placement" in lowered or "proposal" in lowered or "result" in lowered:
        return "Сведения о результатах процедуры", "сведения о результатах"
    if role == "notice" or "notification" in lowered or "извещ" in lowered:
        return "Извещение о закупке", "извещение"
    if _HASH_NAME.fullmatch(name):
        return "Документ закупки", "документ"
    return "Документ закупки", "документ"


def _public_document_inventory(metadata: dict[str, Any]) -> list[dict[str, str]]:
    inventory = []
    for index, item in enumerate(metadata.get("files", []), start=1):
        if not isinstance(item, dict):
            continue
        name, kind = _customer_document_label(item)
        if name == "Извещение о закупке":
            name = f"Извещение о закупке — часть {index}"
        elif name == "Документ закупки":
            name = f"Документ закупки {index}"
        inventory.append({"name": name, "type": kind})
    if inventory and all(item["type"] == "извещение" for item in inventory):
        return [{"name": f"Извещение о закупке — {len(inventory)} структурированных файлов", "type": "извещение"}]
    return inventory


def _format_source_location(value: Any) -> str:
    if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
        return f"позиция {value}"
    text = re.sub(r"[0-9a-f]{64}(?:\.[a-z0-9]+)?(?::row:)?", "", str(value or ""), flags=re.IGNORECASE).strip(": ")
    match = re.search(r"row:(\d+)", text)
    if match:
        return f"раздел «Объект закупки», позиция {match.group(1)}"
    return text if text and not _HASH_NAME.fullmatch(text) else "раздел документа"


def _russian_datetime(value: Any) -> str:
    text = str(value or "").strip()
    if "T" in text:
        parsed = _parse_timestamp(text)
        if parsed:
            return parsed.strftime("%d.%m.%Y %H:%M") + (" (UTC)" if parsed.utcoffset() and parsed.utcoffset().total_seconds() == 0 else "")
    match = re.match(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}:\d{2})(?::\d{2}(?:\.\d+)?)?\s*([+-]\d{2}:\d{2})?", text)
    if not match:
        return text or UNKNOWN
    zone = {"+12:00": " (UTC+12)", "+03:00": " (UTC+3)"}.get(match.group(5), "")
    return f"{match.group(1)}.{match.group(2)}.{match.group(3)} {match.group(4)}{zone}"


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if "T" in text:
            return datetime.fromisoformat(text)
        match = re.match(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s*([+-]\d{2}:\d{2})", text)
        return datetime.fromisoformat(f"{match.group(3)}-{match.group(2)}-{match.group(1)}T{match.group(4)}{match.group(5)}") if match else None
    except ValueError:
        return None


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"[^0-9,.-]", "", value).replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def _quality_gate_status(item: dict[str, Any], name: str, quantity: Any, unit: Any) -> str:
    if item.get("scope_classification_conflict"):
        return "scope_classification_conflict"
    if item.get("procurement_scope_type") in {"works", "services"}:
        return "procurement_scope_mismatch"
    if not item.get("name_source_type") or item.get("name_source_type") == "unresolved":
        return "missing_source_provenance"
    if quantity is None and item.get("quantity_source_path"):
        return "quantity_source_unverified"
    if len(name.split()) <= 3 and not item.get("key_characteristics") and not item.get("characteristics"):
        return "generic_item_name"
    return "valid"


def _procurement_volume_status(items: list[dict[str, Any]], category: str | None) -> tuple[str, str]:
    """Determine volume from row-level evidence; never sum incompatible units."""
    if category not in {"goods", "services", "mixed"}:
        return "not_applicable", "Объём не выражается товарными количествами."
    if not items:
        return "not_specified_in_source", "В доступных документах не найдено товарных позиций с количеством."
    specified = [bool(row.get("quantity") not in (None, "") and row.get("unit_normalized")) for row in items]
    if all(specified):
        return "known", "Каждая извлечённая товарная позиция содержит подтверждённые количество и единицу измерения."
    if any(specified):
        return "partially_known", "Количество и единица подтверждены только для части позиций."
    return "not_specified_in_source", "Количество не зафиксировано в доступных строках источника."


def _format_okpd2_codes(codes: list[dict[str, Any]]) -> list[str]:
    return [f"{item['code']} — {item['name']}" for item in codes]


def _item_rows(preliminary: dict[str, Any]) -> list[dict[str, Any]]:
    """Compatibility facade: resolves patched helpers at call time."""
    from src.modules.tender_operator_agent_demo.operator_report_item_rows import build_item_rows

    return build_item_rows(
        preliminary,
        get_settings=get_settings,
        _format_source_location=_format_source_location,
        _quality_gate_status=_quality_gate_status,
        UNKNOWN=UNKNOWN,
    )


def build_procurement_report_model(metadata: dict[str, Any], outputs: dict[str, dict[str, Any]], *, repository_sha: str = "unknown") -> dict[str, Any]:
    """Legacy stable facade: runtime helper overrides remain effective."""
    from src.modules.tender_operator_agent_demo.operator_report_model_builder import (
        build_procurement_report_model as _build_model,
    )

    return _build_model(
        metadata,
        outputs,
        repository_sha=repository_sha,
        _item_rows=_item_rows,
        _procurement_volume_status=_procurement_volume_status,
        _public_document_inventory=_public_document_inventory,
        _format_source_location=_format_source_location,
        UNKNOWN=UNKNOWN,
        _customer_display_name=_customer_display_name,
        _parse_timestamp=_parse_timestamp,
        _number=_number,
        _russian_datetime=_russian_datetime,
        _format_okpd2_codes=_format_okpd2_codes,
    )


def canonical_report_to_markdown(model: dict[str, Any]) -> str:
    meta, summary, passport = model["metadata"], model["executive_summary"], model["procurement_passport"]
    lines = [f"# Анализ закупки {meta.get('procurement_number') or ''}", "", f"- Название закупки: {model.get('procurement_title') or summary['subject']}", f"- Номер закупки: {model.get('procurement_number')}", f"- Дата публикации: {model.get('publication_datetime')}", f"- Окончание подачи заявок: {model.get('application_deadline')}", f"- НМЦК: {model.get('nmck')} {model.get('currency')}", f"- Решение: {model.get('decision')}", "", "## Резюме для принятия решения", f"- Предмет: {summary['subject']}", f"- Строк состава закупки: {summary['service_item_count']}/{summary['analyzed_item_count']} проанализировано"]
    lines += [f"- Блокер: {value}" for value in summary["blockers"]] or ["- Блокеры: не выявлены автоматически"]
    lines += ["", "## Паспорт закупки", f"- Категория: {passport.get('category')}", f"- ОКПД2: {passport.get('okpd2')}", "", "## Состав и объём закупки"]
    if not model["line_items"]:
        lines.append("- Позиции и количество не удалось извлечь из доступных документов; требуется проверка первоисточника.")
    for row in model["line_items"]:
        evidence = ", ".join(row["evidence_ids"])
        lines.append(f"- {row['sequence']}. {row['original_name']} | количество: {row['quantity_display']} | единица: {row['unit_original']} | статус количества: {row['quantity_status']} | источник: {row['source_document_id']} строка {row['source_row']} | [{evidence}]")
    lines += ["", "## Недостающие данные"] + [f"- {item['description']}: {item['required_action']}" for item in model["missing_data"]]
    lines += ["", "## Риски"] + [f"- {risk.get('risk')}: {risk.get('impact')}" for risk in model["risks"]]
    lines += ["", "## Вопросы"] + [f"- {question}" for question in model["customer_questions"]]
    lines += ["", "## Evidence map"] + [f"- [{item['evidence_id']}] {item['document']}, строка {item['row']}: {item['short_excerpt']}" for item in model["evidence_map"]]
    lines += ["", "## Ограничения анализа"] + [f"- {item}" for item in model["limitations"]]
    return "\n".join(lines)
