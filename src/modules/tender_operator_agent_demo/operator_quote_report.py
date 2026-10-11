"""Product-owned projection of extracted supplier quote comparison.

This is not a quotation extractor: values and supplier identities come only
from the upstream parser or operator-supplied quote inputs. Missing evidence
remains flagged for manual work instead of fabricating offers/prices.
"""
from __future__ import annotations

from typing import Any


def build_quote_comparison_report(
    tkp_comparison: dict[str, Any] | None,
    quote_inputs_present: bool,
    quote_files_present: bool,
    analysis_mode: str,
) -> dict[str, Any]:
    return {
        "status": (
            tkp_comparison.get("status", "blocked")
            if tkp_comparison
            else ("needs_review" if quote_inputs_present else "blocked")
        ),
        "analysis_mode": tkp_comparison.get("analysis_mode", analysis_mode) if tkp_comparison else analysis_mode,
        "supplier_quotes_found": tkp_comparison.get("supplier_quotes_found", 0) if tkp_comparison else 0,
        "items_extracted": tkp_comparison.get("items_extracted", 0) if tkp_comparison else 0,
        "suppliers": tkp_comparison.get("suppliers", []) if tkp_comparison else [],
        "items": tkp_comparison.get("items", []) if tkp_comparison else [],
        "comparison_summary": tkp_comparison.get("comparison_summary", {}) if tkp_comparison else {},
        "warnings": tkp_comparison.get("warnings", []) if tkp_comparison else [],
        "limitations": tkp_comparison.get("limitations", []) if tkp_comparison else [],
        "highlights": (
            [
                f"Найдено распознанных ТКП: {tkp_comparison.get('supplier_quotes_found', 0)}.",
                f"Извлечено сопоставимых позиций: {tkp_comparison.get('items_extracted', 0)}.",
                "Сравнение выполнено локально, в детерминированном демо-режиме без внешних действий.",
            ]
            if tkp_comparison
            else [
                "ТКП загружены, но не распознаны как структурированные таблицы для автоматического сравнения.",
                "Нужна ручная проверка цен, сроков и гарантий по исходным файлам или повторная загрузка ТКП в XLS/XLSX.",
            ]
            if quote_files_present
            else [
                "ТКП не загружены или не распознаны как структурированные таблицы.",
                "Агент подготовил RFQ и список вопросов для дальнейшей ручной работы.",
            ]
        ),
        "manual_checks": (
            [item.get("message", "") for item in tkp_comparison.get("manual_checks", [])]
            if tkp_comparison
            else []
        )
        or (
            ["Проверить реальные значения цены, срока и гарантий по загруженным ТКП."]
            if quote_files_present
            else ["Собрать ТКП вручную и повторно запустить анализ после загрузки коммерческих предложений."]
        ),
    }

