"""Product-owned evidence-facing trace for a procurement analysis report.

Projection only: preserves source/role counts and human-review limitations
from the actual analyzed documents; no I/O or autonomous external actions.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_operator_analysis_trace(
    *,
    documents: list[Any],
    metadata: dict[str, Any],
    preliminary_analysis: dict[str, Any],
    rich_documents: list[Any],
    source_facts: list[Any],
    requirement_rows: list[dict[str, Any]],
    procurement_kind: str,
    rationale: list[str],
    output_warnings: list[str],
    semantic_procurement_role: Callable[[Any], str],
) -> dict[str, Any]:
    return {
        "documents_considered": [doc.display_name for doc in documents],
        "procurement_context": {
            "source": metadata.get("procurement_source"),
            "procurement_id": metadata.get("procurement_id"),
            "procurement_url": metadata.get("procurement_url"),
            "attachments_status": metadata.get("attachments_status"),
        },
        "fields_extracted": [
            *preliminary_analysis.get("extracted_fields", []),
        ],
        "risk_signals": [
            "При отсутствии LLM используется документ-зависимый детерминированный анализ без шаблонов из чужой предметной области.",
            "Внешние действия отключены по design policy.",
            "Нормализация Excel-таблиц использует deterministic parser + heuristics без LLM.",
            "Часть выводов требует ручного подтверждения по исходным файлам.",
        ],
        "document_analysis_policy": "source_first_all_text_v1",
        "document_role_policy": "content_aware_procurement_role_v1",
        "requirements_generation_policy": "source_derived_goods_v1",
        "source_extraction_summary": {
            "documents_total": len(documents),
            "text_bearing_documents": sum(bool(doc.text) for doc in documents),
            "rich_documents": len(rich_documents),
            "rich_documents_with_facts": len({fact.file_id for fact in source_facts if any(doc.file_id == fact.file_id for doc in rich_documents)}),
            "source_facts_extracted": len(source_facts),
            "source_derived_requirements": sum(bool(row.get("source_fact_id")) for row in requirement_rows) if procurement_kind == "goods" else 0,
            "template_requirements": sum(not row.get("source_fact_id") for row in requirement_rows) if procurement_kind == "goods" else 0,
            "semantic_roles": {doc.file_id: semantic_procurement_role(doc) for doc in documents if doc.text},
        },
        "decision_factors": rationale,
        "overall_explanation": (
            "Агент использовал локально загруженные файлы, безопасное извлечение текста и документ-зависимый детерминированный анализ. "
            "Если LLM недоступен или ТКП отсутствуют, интерфейс показывает предметные выводы по документам и честно отмечает ограничения вместо подстановки шаблонов из другой предметной области."
        ),
        "per_step": {
            "documents": "Файлы сохранены локально, имена нормализованы, опасные пути отброшены.",
            "requirements": "Требования и предварительный анализ собраны из ТЗ, извещения, проекта договора и документа по заявке с безопасным локальным извлечением текста.",
            "questions": "Сформирован список вопросов для ручной коммуникации с поставщиками.",
            "rfq": "Подготовлен draft RFQ для ручной отправки вне системы.",
            "quotes": "Сравнение ТКП использует детерминированный парсер таблиц и честно помечает частичные результаты и зоны ручной проверки.",
            "economics": "Экономика строится только на доступных локальных данных и операторских параметрах, без выдуманной выручки.",
            "risks": "Риски агрегированы из доступного контракта и ограничений demo-mode.",
            "decision": "Итог всегда требует подтверждения человеком и не приводит к внешним действиям.",
        },
        "human_control_note": "Демо- и пилотный режим. Нет подачи заявок, писем, ЭЦП или действий на площадках без человека.",
        "limitations": metadata.get("limitations", []) + output_warnings,
    }

