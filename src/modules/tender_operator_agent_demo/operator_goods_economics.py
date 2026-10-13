"""Business projection for goods economics; unknown supplier prices stay unknown.

Generic extraction/search belongs to Data Platform. The product-owned economic
fallback receives those source/helper functions explicitly, without importing
the legacy upload monolith or querying outside systems.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_goods_economics_payload(
    metadata: dict[str, Any],
    documents: list[Any],
    analysis_mode: str,
    economics: dict[str, Any] | None,
    *,
    collect_goods_items: Callable[[list[Any]], list[Any]],
    extract_notice_price: Callable[..., str | None],
    collect_role_text: Callable[..., str],
    parse_float: Callable[..., float | None],
    format_decimal_price: Callable[..., str],
) -> dict[str, Any]:
    if economics:
        payload = dict(economics)
        payload.setdefault("analysis_mode", analysis_mode)
        payload.setdefault("economics_status", "needs_review")
        payload.setdefault("result", "Экономика требует ручной проверки")
        payload.setdefault("drivers", ["Сопоставление ТКП требует ручного подтверждения."])
        payload["manual_checks"] = [
            item.get("message", item.get("code", "Проверить расчёт по исходным ТКП вручную."))
            if isinstance(item, dict)
            else str(item)
            for item in payload.get("manual_checks", [])
        ] or ["Проверить расчёт по исходным ТКП вручную."]
        payload.setdefault("metrics", [
            {"label": "Минимальная закупочная стоимость", "value": payload.get("supplier_cost_min", "не определена")},
            {"label": "Предварительная цена подачи", "value": payload.get("preliminary_bid_price", "не определена")},
            {"label": "Целевая маржа", "value": payload.get("gross_margin_percent", "не определена")},
        ])
        return payload
    items = collect_goods_items(documents)
    nmck = extract_notice_price(metadata, collect_role_text(documents, "technical_spec"), collect_role_text(documents, "contract_draft"), collect_role_text(documents, "notice"))
    total_quantity = sum(parse_float(item.quantity) or 0 for item in items if (item.unit or "") == "м")
    nmck_value = parse_float(nmck.replace(" ", "") if nmck else None)
    avg_price = (nmck_value / total_quantity) if nmck_value is not None and total_quantity else None
    metrics = [
        {"label": "НМЦК", "value": f"{nmck} руб." if nmck else "не указана"},
        {"label": "Цена закупки", "value": "не определена, требуется КП поставщика"},
        {"label": "Что запросить", "value": "цену за единицу и сумму по каждой позиции"},
        {"label": "Что запросить", "value": "включены ли доставка и разгрузка"},
        {"label": "Что запросить", "value": "НДС, срок действия КП и наличие на складе"},
        {"label": "Общий объём", "value": f"{int(total_quantity) if float(total_quantity).is_integer() else total_quantity} м" if total_quantity else "не рассчитан"},
        {"label": "Ориентир по НМЦК на метр", "value": f"{format_decimal_price(avg_price)} руб./м" if avg_price is not None else "не рассчитан"},
    ]
    return {
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
        "result": "Экономика требует запроса КП по товарным позициям",
        "status": "blocked",
        "metrics": metrics,
        "drivers": [
            "Экономика построена по НМЦК и извлечённым позициям поставки без подмены software/integration шаблонами.",
            "Для решения нужны реальные КП по каждой позиции, включая доставку и документы качества.",
        ],
        "manual_checks": [
            "Запросить цену за единицу и сумму по каждой позиции.",
            "Проверить, включены ли доставка, разгрузка, НДС и упаковка.",
            "Сверить наличие товара и срок поставки в течение 15 рабочих дней по заявке.",
        ],
        "warnings": [],
        "limitations": [],
        "assumptions": {"supply_items_count": len(items)},
    }
