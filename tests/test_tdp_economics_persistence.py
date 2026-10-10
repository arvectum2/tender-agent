"""Persisted quote/economics adapters must preserve missing-source and review gates."""

import json
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_economics_persistence import (
    _coerce_economics_summary_payload,
    _coerce_quote_comparison_payload,
    _maybe_float,
    _serialize_economics_summary,
    _serialize_quote_comparison,
)


def test_facade_retains_exact_adapters():
    for name in (
        "_coerce_quote_comparison_payload",
        "_coerce_economics_summary_payload",
        "_maybe_float",
        "_serialize_quote_comparison",
        "_serialize_economics_summary",
    ):
        from src.modules.tender_operator_agent_demo import (
            operator_economics_persistence as core,
        )

        assert getattr(legacy, name) is getattr(core, name)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("unknown", None),
        ("unknown value", None),
        ("incorrect", None),
        ("2450.25", 2450.25),
        (0, 0.0),
    ],
)
def test_unknown_and_unreadable_prices_not_invented(value, expected):
    assert _maybe_float(value) == expected


def test_empty_quote_and_economics_are_blocked_review_only():
    quote = _coerce_quote_comparison_payload({})
    economics = _coerce_economics_summary_payload({})
    assert quote.status == economics.status == "blocked"
    assert quote.analysis_mode == economics.analysis_mode == "unknown"
    assert quote.supplier_quotes_found == 0
    assert quote.items_extracted == 0
    assert quote.suppliers == []
    assert economics.supplier_cost_min is None
    assert economics.supplier_cost_selected is None
    assert economics.preliminary_bid_price is None
    assert economics.gross_margin_percent is None
    assert economics.economics_status == "insufficient_data"


def test_legacy_supplier_price_missing_remains_none_and_requires_review():
    payload = {
        "status": "needs_review",
        "analysis_mode": "fallback_deterministic_adapter",
        "supplier_quotes_found": 1,
        "suppliers": [
            {
                "supplier": "ООО «Поставщик»",
                "price_total": "unknown",
                "source_file": "Исходное КП.xlsx",
            }
        ],
        "manual_checks": ["Проверить цену по оригиналу"],
        "warnings": ["Цена не подтверждена"],
        "limitations": ["without verified price"],
    }
    result = _coerce_quote_comparison_payload(payload)
    assert result.suppliers[0].supplier_id == "SUP-01"
    assert result.suppliers[0].supplier_name == "ООО «Поставщик»"
    assert result.suppliers[0].source_file == "Исходное КП.xlsx"
    assert result.suppliers[0].total_amount is None
    assert result.suppliers[0].document_type == "legacy_quote_placeholder"
    assert result.manual_checks[0].message == "Проверить цену по оригиналу"
    assert result.warnings[0].message == "Цена не подтверждена"
    assert result.limitations == ["without verified price"]
    dumped = _serialize_quote_comparison(result)
    assert dumped["suppliers"][0]["total_amount"] is None
    assert dumped["analysis_mode"] == "fallback_deterministic_adapter"


def test_typed_supplier_keeps_original_identity_and_amount():
    existing = {
        "supplier_id": "SUP-EIS-11",
        "supplier_name": "ООО «Контрагент»",
        "source_file": "КП.pdf",
        "document_type": "commercial_quote",
        "total_amount": 135000.5,
        "items_count": 0,
    }
    comparison = _coerce_quote_comparison_payload(
        {
            "status": "review",
            "analysis_mode": "source_locked",
            "supplier_quotes_found": 1,
            "suppliers": [existing],
        }
    )
    assert comparison.suppliers[0].supplier_id == "SUP-EIS-11"
    assert comparison.suppliers[0].total_amount == 135000.5


def test_economics_retains_unknowns_manual_review_and_original_assumptions():
    summary = _coerce_economics_summary_payload(
        {
            "status": "blocked",
            "analysis_mode": "unknown",
            "economics_status": "insufficient_data",
            "currency": "RUB",
            "assumptions": {"Поставка": "Не подтверждена"},
            "warnings": ["КП отсутствует"],
            "manual_checks": ["Запросить предложение"],
        }
    )
    assert summary.supplier_cost_min is None
    assert summary.gross_margin_amount is None
    assert summary.assumptions == {"Поставка": "Не подтверждена"}
    assert summary.manual_checks[0].message == "Запросить предложение"
    assert summary.warnings[0].message == "КП отсутствует"
    assert _serialize_economics_summary(summary)["gross_margin_amount"] is None


def test_persisted_roundtrip_keeps_absent_fields_unknown(tmp_path: Path):
    first = _serialize_economics_summary(_coerce_economics_summary_payload({}))
    path = tmp_path / "economics.json"
    path.write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
    restored = _coerce_economics_summary_payload(
        json.loads(path.read_text(encoding="utf-8")),
    )
    assert restored.model_dump(mode="json") == first
    assert restored.economics_status == "insufficient_data"
