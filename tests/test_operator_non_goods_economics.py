"""Contracts for source-conservative non-goods Tender Agent economics."""

from __future__ import annotations

import pytest

from src.modules.tender_operator_agent_demo.operator_non_goods_economics import (
    build_non_goods_economics_payload,
)


def project(kind="services", economics=None, *, nmck="250000", service_items=None):
    called = []

    def notice_price(*_parts):
        called.append("notice")
        return nmck

    result = build_non_goods_economics_payload(
        {"tender_title": "Сопровождение системы"},
        "Техническое задание",
        "Проект контракта",
        "Извещение",
        "fallback_deterministic_adapter",
        {"service_items": service_items if service_items is not None else []},
        economics,
        kind,
        _extract_notice_price=notice_price,
    )
    return result, called


def test_services_without_verified_costs_are_blocked_and_do_not_invent_profit():
    result, called = project(
        "services",
        service_items=[{"description": "Монтаж"}, {"description": "Настройка"}],
    )
    assert called == ["notice"]
    assert result["status"] == "blocked"
    assert result["economics_status"] == "insufficient_data"
    assert result["supplier_cost_min"] is None
    assert result["supplier_cost_selected"] is None
    assert result["expected_revenue"] is None
    assert result["preliminary_bid_price"] is None
    assert result["gross_margin_amount"] is None
    assert result["gross_margin_percent"] is None
    assert result["cash_gap_estimate"] is None
    assert result["assumptions"] == {}
    assert result["metrics"][0] == {"label": "НМЦК", "value": "250000"}
    assert result["metrics"][1] == {"label": "Единичные расценки", "value": "извлечено строк: 2"}
    assert any("не рассчитывались" in x for x in result["warnings"])


def test_services_missing_notice_price_does_not_fabricate_nmck():
    result, called = project("services", nmck=None)
    assert called == ["notice"]
    assert result["metrics"][0]["value"] == "не указана"
    assert result["expected_revenue"] is None


@pytest.mark.parametrize("kind", ["integration", "license", "mixed", "generic", "unresolved"])
def test_other_procurements_missing_economic_input_require_quote_or_labor_estimate(kind):
    result, called = project(kind, nmck=None)
    assert called == ["notice"]
    assert result["status"] == "blocked"
    assert result["supplier_cost_min"] is None
    assert result["expected_revenue"] is None
    assert result["gross_margin_percent"] is None
    assert result["preliminary_bid_price"] is None
    assert result["metrics"][0]["value"] == "не указана"
    assert any("оценка трудозатрат" in x["value"] for x in result["metrics"] if x["label"] == "Что запросить")


def test_confirmed_operator_inputs_retained_without_repricing_or_notice_lookup():
    economics = {
        "analysis_mode": "operator",
        "currency": "RUB",
        "economics_status": "conditionally_viable",
        "status": "needs_review",
        "supplier_cost_min": 20000,
        "supplier_cost_selected": 26000,
        "expected_revenue": 70000,
        "preliminary_bid_price": 68000,
        "gross_margin_amount": 42000,
        "gross_margin_percent": 60,
        "cash_gap_estimate": 4000,
        "selected_supplier_name": "Поставщик",
        "warnings": ["Ограниченная полнота ТКП"],
        "manual_checks": [{"code": "source", "message": "Сверить ТКП с оригиналом"}],
    }
    result, called = project("services", economics)
    assert called == []
    assert result["status"] == "needs_review"
    assert result["economics_status"] == "conditionally_viable"
    assert result["supplier_cost_min"] == 20000
    assert result["gross_margin_percent"] == 60
    assert result["preliminary_bid_price"] == 68000
    assert result["manual_checks"] == ["Сверить ТКП с оригиналом"]
    assert result["warnings"] == ["Ограниченная полнота ТКП"]
    assert economics["manual_checks"][0]["code"] == "source"


def test_unknown_explicit_margin_is_not_turned_into_zero_or_success():
    result, called = project(
        "license",
        {"economics_status": "insufficient_data", "gross_margin_percent": None},
    )
    assert called == []
    assert result["gross_margin_percent"] is None
    margin = next(x["value"] for x in result["metrics"] if x["label"] == "Целевая маржа")
    assert margin == "unknown"
    assert result["status"] == "blocked"


def test_supplied_economics_with_string_message_requires_source_review():
    result, _ = project(
        "integration",
        {
            "supplier_cost_min": None,
            "warnings": ["Проверить основание"],
            "manual_checks": [{"message": "Проверить требования в ТЗ"}],
        },
    )
    assert result["supplier_cost_min"] is None
    assert result["manual_checks"] == ["Проверить требования в ТЗ"]
    assert result["warnings"] == ["Проверить основание"]
