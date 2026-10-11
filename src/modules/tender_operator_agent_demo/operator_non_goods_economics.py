"""Product-owned economics projection for service and non-goods procurements.

Source-derived NMCK is informative only. When no verified costs/quotes
exist, no supplier cost, bid price, profitability or cash gap is invented.
This module performs no I/O and reuses the legacy notice-price extractor.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_non_goods_economics_payload(
    metadata: dict[str, Any],
    technical_spec_text: str,
    contract_draft_text: str,
    notice_text: str,
    analysis_mode: str,
    preliminary_analysis: dict[str, Any],
    economics: dict[str, Any] | None,
    procurement_kind: str,
    *,
    _extract_notice_price: Callable[..., str | None],
) -> dict[str, Any]:
    if procurement_kind == "services" and not economics:
        service_items = preliminary_analysis.get("service_items", [])
        economics_payload = {
            "analysis_mode": analysis_mode,
            "currency": "RUB",
            "economics_status": "insufficient_data",
            "supplier_cost_min": None,
            "supplier_cost_selected": None,
            "expected_revenue": None,
            "preliminary_bid_price": None,
            "gross_margin_amount": None,
            "gross_margin_percent": None,
            "logistics_reserve": None,
            "risk_reserve": None,
            "payment_delay_days": None,
            "cash_gap_estimate": None,
            "selected_supplier_name": None,
            "result": "Экономика не рассчитана: отсутствуют фактический объём и подтверждённые коммерческие входы.",
            "status": "blocked",
            "metrics": [
                {"label": "НМЦК", "value": _extract_notice_price(metadata, technical_spec_text, contract_draft_text, notice_text) or "не указана"},
                {"label": "Единичные расценки", "value": f"извлечено строк: {len(service_items)}"},
                {"label": "Фактический объём", "value": "не определён документацией"},
                {"label": "Что запросить", "value": "внутренняя стоимость нормо-часа и стоимость релевантных операций"},
                {"label": "Что запросить", "value": "подход к учёту материалов, запасных частей и логистики"},
                {"label": "Что запросить", "value": "проект контракта и условия оплаты/обеспечения"},
            ],
            "drivers": ["НМЦК и единичные расценки не являются прибылью или ожидаемой выручкой без объёма услуг."],
            "manual_checks": ["Собрать коммерческие входы и сопоставить расценки с себестоимостью до финансового решения."],
            "warnings": ["Экономические результаты, маржа и рентабельность не рассчитывались."],
            "limitations": ["Фактический объём, себестоимость, поставщик и проект контракта отсутствуют."],
            "assumptions": {},
        }
    else:
        economics_payload = {
            "analysis_mode": economics.get("analysis_mode", analysis_mode) if economics else analysis_mode,
            "currency": economics.get("currency", "RUB") if economics else "RUB",
            "economics_status": economics.get("economics_status", "insufficient_data") if economics else "insufficient_data",
            "supplier_cost_min": economics.get("supplier_cost_min") if economics else None,
            "supplier_cost_selected": economics.get("supplier_cost_selected") if economics else None,
            "expected_revenue": economics.get("expected_revenue") if economics else None,
            "preliminary_bid_price": economics.get("preliminary_bid_price") if economics else None,
            "gross_margin_amount": economics.get("gross_margin_amount") if economics else None,
            "gross_margin_percent": economics.get("gross_margin_percent") if economics else None,
            "logistics_reserve": economics.get("logistics_reserve") if economics else None,
            "risk_reserve": economics.get("risk_reserve") if economics else None,
            "payment_delay_days": economics.get("payment_delay_days") if economics else None,
            "cash_gap_estimate": economics.get("cash_gap_estimate") if economics else None,
            "selected_supplier_name": economics.get("selected_supplier_name") if economics else None,
            "result": (
                "Экономика требует запроса КП / оценки подрядчика"
                if not economics
                else (
                    "Экономика выглядит условно приемлемой"
                    if economics.get("economics_status") == "conditionally_viable"
                    else "Экономика требует ручной проверки"
                )
            ),
            "status": economics.get("status", "blocked") if economics else "blocked",
            "metrics": (
                [
                    {"label": "НМЦК", "value": _extract_notice_price(metadata, technical_spec_text, contract_draft_text, notice_text) or "не указана"},
                    {"label": "Закупочная себестоимость", "value": "не определена, требуется ТКП/оценка подрядчика"},
                    {"label": "Что запросить", "value": "оценка трудозатрат по предмету закупки"},
                    {"label": "Что запросить", "value": "коммерческие входы, подтверждающие себестоимость и риски"},
                ]
                if not economics
                else [
                    {"label": "Минимальная закупочная стоимость", "value": economics.get("supplier_cost_min", "unknown")},
                    {"label": "Выбранная закупочная стоимость", "value": economics.get("supplier_cost_selected", "unknown")},
                    {"label": "Резерв логистики", "value": economics.get("logistics_reserve", "unknown")},
                    {"label": "Резерв риска", "value": economics.get("risk_reserve", "unknown")},
                    {"label": "Целевая маржа", "value": f"{economics.get('gross_margin_percent')}%" if economics.get("gross_margin_percent") is not None else "unknown"},
                    {"label": "Предварительная цена подачи", "value": economics.get("preliminary_bid_price", "unknown")},
                    {"label": "Оценка кассового разрыва", "value": economics.get("cash_gap_estimate", "unknown")},
                ]
            ),
            "drivers": (
                [
                    f"Выбран поставщик: {economics.get('selected_supplier_name') or 'не определён'}.",
                    "Ожидаемая выручка не рассчитывается автоматически без цены заказчика.",
                    "Расчёт построен на локальных ТКП и операторских параметрах из демо-формы.",
                ]
                if economics
                else ["Без КП и оценки трудозатрат экономика ограничивается НМЦК и перечнем данных, которые нужно запросить."]
            ),
            "manual_checks": ([item.get("message", "") for item in economics.get("manual_checks", [])] if economics else [])
            or ["Запросить КП/оценку подрядчика по подтверждённому предмету закупки."],
            "warnings": economics.get("warnings", []) if economics else [],
            "limitations": economics.get("limitations", []) if economics else [],
            "assumptions": economics.get("assumptions", {}) if economics else {},
        }

    return economics_payload
