"""Owner-only scenario sensitivity; never classify assumed margin as bid-ready."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.acceptance.museum_multimedia_three_complex_budget import (
    CostScenario,
    build,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = json.loads((ROOT / "docs/roadmap/b2b_priority_eis_documents_2026-10-17.json").read_text())
MATRIX = json.loads((ROOT / "docs/roadmap/b2b_priority_three_matrix_2026-10-17.json").read_text())
RESULT = json.loads((
    ROOT / "docs/roadmap/b2b_museum_three_exhibits_cost_sensitivity_2026-10-17.json"
).read_text())


def test_scenarios_bound_to_authentic_original_eis_not_market_quotes():
    assert RESULT["schema_version"] == "arvectum-three-exhibit-museum-cost-sensitivity-v1"
    assert RESULT["source_original_44fz_notice_number"] == "0161600001326000063"
    assert RESULT["source_nmck_rub"] == "1600000.00"
    assert RESULT["source_museum_interactive_programs_count"] == 3
    museum = next(x for x in MATRIX["cases"] if x["id"] == RESULT["source_original_44fz_notice_number"])
    assert museum["contract_warranty_months"] == RESULT["source_warranty_months"] == 12
    assert museum["required_contract_finish"] == RESULT["source_contract_completion_by"]
    assert museum["contract_performance_security_percent_of_final_price"] == 5
    assert len([
        x for x in SOURCE["procedures"] if x["procurement_number"] == museum["id"]
        and x["successfully_retrieved_attachment_count"] == 7
    ]) == 1
    assert RESULT["source_original_attachment_sha_verified"] is True
    assert RESULT["costs_from_customer_or_vendors_verified"] is False
    assert RESULT["bid_authorization"] is False
    assert RESULT["tax_assumption_usn_income_six_percent_not_final_statutory_calculation"] is True
    assert RESULT["vat_treatment_legally_verified"] is False
    assert RESULT["payment_stages_confirmed"] is False
    assert RESULT["testing_remote_permitted_verified"] is False


@pytest.mark.parametrize("name,cash,labor,profit,breakeven", [
    ("lean_remote_unconfirmed", "295000.00", "600000.00", "609000.00", "952127.66"),
    ("baseline_one_site_visit_unconfirmed", "765000.00", "840000.00", "-101000.00", "1707446.81"),
    ("stress_remote_is_not_accepted_unconfirmed", "1350000.00", "1500000.00", "-1346000.00", "3031914.89"),
])
def test_three_first_party_scope_but_hypothetical_prices_no_go(
    name, cash, labor, profit, breakeven
):
    record = next(x for x in RESULT["scenarios"] if x["scenario_id"] == name)
    assert record["assumption_basis"] == "AUTHOR_HYPOTHESIS_NOT_PROVIDER_QUOTE_NOT_SOURCE_COST"
    assert len(record["cash_budget_hypothetical_rub"]) == 7
    assert record["internal_own_labor_estimate_not_external_payment_hours"] > 0
    assert record["internal_own_labor_shadow_rate_not_a_quote_rub_per_hour"] > 0
    assert len(record["price_variants"]) == 4
    rows = record["price_variants"]
    assert [r["price_discount_percent"] for r in rows] == [
        "0.00", "10.00", "20.00", "25.00",
    ]
    for row in rows:
        assert row["cash_external_illustrative_rub"] == cash
        assert row["shadow_own_labor_economic_cost_rub"] == labor
        assert row["economic_break_even_price_rub"] == breakeven
        assert row["eligible_to_submit"] is False
        assert row["owner_legal_go"] is False and row["owner_commercial_go"] is False
        bid = Decimal(row["assumed_bid_price_rub"])
        tax = Decimal(row["usn_six_percent_gross_planning_tax_rub"])
        sec = Decimal(row["liquidity_performance_security_5pct_rub"])
        assert tax == bid * Decimal("0.06")
        assert sec == bid * Decimal("0.05")
        assert Decimal(row["economic_profit_after_shadow_labor_and_usn_rub"]) == (
            bid - Decimal(cash) - Decimal(labor) - tax
        )
        assert Decimal(row["cash_after_illustrative_external_cost_and_usn_before_labor_rub"]) == (
            bid - Decimal(cash) - tax
        )
        assert Decimal(row["approx_upfront_cash_plus_security_upper_bound_rub"]) == (
            Decimal(cash) + sec
        )
        assert row["at_or_above_25pct_discount_extra_antidumping_review"] is (
            row["price_discount_percent"] == "25.00"
        )
    assert rows[0]["economic_profit_after_shadow_labor_and_usn_rub"] == profit
    assert Decimal(rows[-1]["economic_profit_after_shadow_labor_and_usn_rub"]) < Decimal(profit)


def test_cash_security_is_not_double_counted_as_economic_expense():
    for s in RESULT["scenarios"]:
        for r in s["price_variants"]:
            cash = Decimal(r["cash_external_illustrative_rub"])
            shadow = Decimal(r["shadow_own_labor_economic_cost_rub"])
            bid = Decimal(r["assumed_bid_price_rub"])
            tax = Decimal(r["usn_six_percent_gross_planning_tax_rub"])
            assert Decimal(r["economic_profit_after_shadow_labor_and_usn_rub"]) == (
                bid - cash - shadow - tax
            )
            # Security is liquidity tie-up if deposited in cash and not expense.
            assert Decimal(r["approx_upfront_cash_plus_security_upper_bound_rub"]) > cash


@pytest.mark.parametrize("discount", ["-0.01", "0.26", "1.0"])
def test_reject_unbounded_hypothetical_discount(discount):
    s = CostScenario("safe", {str(k): k for k in range(7)}, 100, 1000)
    with pytest.raises(ValueError):
        s.evaluate(bid_discount=Decimal(discount))


@pytest.mark.parametrize("invalid", [
    {"a": -1, "b": 1, "c": 1, "d": 1, "e": 1, "f": 1, "g": 1},
    {"a": 1, "b": 1, "c": 1, "d": 1, "e": 1, "f": 1},
])
def test_reject_missing_or_negative_cash_costs(invalid):
    with pytest.raises(ValueError):
        CostScenario("bad", invalid, 100, 1000)


def test_docs_keep_explicit_unverified_source_market_cost_line():
    report = (ROOT / "docs/roadmap/B2B_MUSEUM_3_COMPLEXES_ECONOMICS_2026-10-17.md").read_text()
    assert "расчётные гипотезы" in report
    assert "не является коммерческим предложением" in report
    assert "1 707 447" in report
    assert "227 500" not in report  # belongs to Yakutia, not museum guarantee
    assert "80 000" in report  # 5% of museum NMC, security as liquidity
    assert "не GO" in report
    assert "Северо-Курильск" in report
    assert "Собственный труд" in report
    assert "25%" in report


def test_no_database_or_network_is_needed_for_cost_planning():
    built = build()
    assert built == RESULT
    assert all(not p["owner_commercial_go"] and not p["eligible_to_submit"]
               for s in built["scenarios"] for p in s["price_variants"])
