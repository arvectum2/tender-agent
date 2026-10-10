"""Economics R3 boundary tests: verified inputs survive and unknown prices stay unknown."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_goods_economics import (
    build_goods_economics_payload,
)


def projection(economics=None, items=None, nmck=None, *, called=None):
    def collect_goods(_documents):
        if called is not None:
            called.append("items")
        return items or []

    return build_goods_economics_payload(
        {"procurement_number": "0372200172326000015"},
        [],
        "fallback_deterministic_adapter",
        economics,
        collect_goods_items=collect_goods,
        extract_notice_price=lambda *_: nmck,
        collect_role_text=lambda *_: "",
        parse_float=lambda value: float(value) if value is not None else None,
        format_decimal_price=lambda value: f"{value:.2f}",
    )


def test_supplied_economics_preserves_values_without_invoking_extraction():
    original = {
        "supplier_cost_min": 120.5,
        "preliminary_bid_price": 250,
        "gross_margin_percent": None,
        "manual_checks": [{"code": "review-cost", "message": "Проверить КП"}, "Сверить НДС"],
        "economics_status": "needs_review",
    }
    called = []
    result = projection(original, called=called)
    assert result["supplier_cost_min"] == 120.5
    assert result["preliminary_bid_price"] == 250
    assert result["gross_margin_percent"] is None
    assert result["manual_checks"] == ["Проверить КП", "Сверить НДС"]
    assert result["analysis_mode"] == "fallback_deterministic_adapter"
    assert original["manual_checks"][0]["code"] == "review-cost"
    assert called == []


@pytest.mark.parametrize("value", [None, {}])
def test_missing_quote_does_not_invent_supplier_cost_bid_or_margin(value):
    result = projection(value, nmck="300")
    assert result["economics_status"] == "insufficient_data"
    assert result["status"] == "blocked"
    assert result["supplier_cost_min"] is None
    assert result["preliminary_bid_price"] is None
    assert result["gross_margin_percent"] is None
    assert result["assumptions"]["supply_items_count"] == 0
    assert "не определена" in str(result["metrics"])


def test_nmck_per_unit_remains_informational_without_supplier_quote():
    items = [
        SimpleNamespace(quantity="2", unit="м"),
        SimpleNamespace(quantity="3", unit="м"),
        SimpleNamespace(quantity="8", unit="шт"),
    ]
    result = projection(items=items, nmck="1000")
    assert result["assumptions"]["supply_items_count"] == 3
    values = {metric["label"]: metric["value"] for metric in result["metrics"]}
    assert values["Общий объём"] == "5 м"
    assert values["Ориентир по НМЦК на метр"] == "200.00 руб./м"
    assert result["supplier_cost_selected"] is None


def test_historical_legacy_facade_identity_and_payload(monkeypatch):
    from src.modules.tender_operator_agent_demo import upload_service

    assert legacy._build_goods_economics_payload is upload_service._build_goods_economics_payload
    monkeypatch.setattr(legacy, "_collect_goods_supply_items_from_documents", lambda _: [])
    monkeypatch.setattr(legacy, "_collect_role_text", lambda *_: "")
    monkeypatch.setattr(legacy, "_extract_notice_price", lambda *_: None)
    actual = legacy._build_goods_economics_payload({}, [], "legacy", None)
    expected = projection()
    assert actual["supplier_cost_min"] == expected["supplier_cost_min"]
    assert actual["metrics"][1:] == expected["metrics"][1:]
    assert actual["analysis_mode"] == "legacy"
