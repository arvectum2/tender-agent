"""Supplier quote report projection must never invent evidence or offers."""

from __future__ import annotations

from src.modules.tender_operator_agent_demo.operator_quote_report import (
    build_quote_comparison_report,
)


def project(quotes=None, *, inputs=False, files=False, mode="fallback"):
    return build_quote_comparison_report(quotes, inputs, files, mode)


def test_missing_quote_inputs_stay_blocked_with_empty_quote_lists():
    result = project()
    assert result["status"] == "blocked"
    assert result["analysis_mode"] == "fallback"
    assert result["supplier_quotes_found"] == 0
    assert result["items_extracted"] == 0
    assert result["suppliers"] == []
    assert result["items"] == []
    assert result["comparison_summary"] == {}
    assert result["warnings"] == []
    assert any("Собрать ТКП" in msg for msg in result["manual_checks"])
    assert any("ТКП не загружены" in msg for msg in result["highlights"])


def test_quote_files_present_but_unparsed_keep_manual_reconciliation():
    result = project(None, inputs=True, files=True)
    assert result["status"] == "needs_review"
    assert result["supplier_quotes_found"] == 0
    assert result["items_extracted"] == 0
    assert result["suppliers"] == []
    assert result["items"] == []
    assert any("не распознаны" in msg for msg in result["highlights"])
    assert any("Проверить реальные значения" in msg for msg in result["manual_checks"])


def test_inputs_declared_without_quote_files_still_no_fabricated_offers():
    result = project(None, inputs=True, files=False)
    assert result["status"] == "needs_review"
    assert result["supplier_quotes_found"] == 0
    assert result["suppliers"] == []
    assert any("Собрать ТКП" in msg for msg in result["manual_checks"])


def test_structured_supplier_quotes_keep_upstream_counts_and_items():
    source = {
        "status": "needs_review",
        "analysis_mode": "deterministic_table",
        "supplier_quotes_found": 1,
        "items_extracted": 2,
        "suppliers": [{"supplier_label": "Поставщик 1"}],
        "items": [{"description": "Стол", "amount": 350}],
        "comparison_summary": {"spreadsheet": True},
        "warnings": ["НДС неизвестен"],
        "limitations": ["Нет подписанного КП"],
        "manual_checks": [{"code": "review", "message": "Сверить НДС с оригиналом"}],
    }
    result = project(source, inputs=True, files=True)
    assert result["status"] == "needs_review"
    assert result["analysis_mode"] == "deterministic_table"
    assert result["supplier_quotes_found"] == 1
    assert result["items_extracted"] == 2
    assert result["suppliers"] == source["suppliers"]
    assert result["items"] == source["items"]
    assert result["comparison_summary"] == source["comparison_summary"]
    assert result["warnings"] == ["НДС неизвестен"]
    assert result["manual_checks"] == ["Сверить НДС с оригиналом"]
    assert source["manual_checks"][0]["code"] == "review"
    assert any("Найдено распознанных ТКП: 1" in item for item in result["highlights"])


def test_upstream_empty_manual_checks_require_operator_verification():
    result = project({"status": "blocked", "supplier_quotes_found": 0}, inputs=True, files=True)
    assert result["status"] == "blocked"
    assert result["manual_checks"] == [
        "Проверить реальные значения цены, срока и гарантий по загруженным ТКП."
    ]
    assert result["items_extracted"] == 0


def test_upstream_comparison_does_not_trigger_submission():
    report = project(
        {"status": "needs_review", "supplier_quotes_found": 0, "items_extracted": 0},
        inputs=True,
        files=True,
    )
    assert "без внешних действий" in report["highlights"][2]
    assert not any("автоматически отправлено" in item for item in report["highlights"])
