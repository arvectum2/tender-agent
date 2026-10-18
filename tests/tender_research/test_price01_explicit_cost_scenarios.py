"""Stateless, hypothetical financial thresholds, never procurement bid suggestions."""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.modules.tender_operator_agent_demo.operator_cost_scenarios import (
    ExplicitCostScenarioRequest,
    calculate_explicit_cost_thresholds,
)

SAMPLE = {
    "external_direct_rub": "100.00",
    "labor_rub": "200.00",
    "reserve_rub": "20.00",
    "fixed_platform_fees_rub": "5.00",
    "revenue_tax_percent": "6",
    "variable_platform_fee_percent": "2",
    "target_profit_rub": "50",
    "accept_hypothetical_assumptions_only": True,
}


def test_stateless_three_explicit_cash_and_economic_thresholds():
    result = calculate_explicit_cost_thresholds(ExplicitCostScenarioRequest(**SAMPLE))
    assert result["state"] == "EXPLICIT_USER_ASSUMPTION_BREAK_EVEN_ONLY"
    assert result["cash_break_even_rub"] == "135.87"
    assert result["full_economic_break_even_rub"] == "353.27"
    assert result["full_cost_plus_explicit_target_rub"] == "407.61"
    assert result["inputs_stored"] is False
    assert result["assumptions_independently_verified"] is False
    assert result["is_procurement_bid_recommendation"] is False
    assert result["probability_of_winning_estimated"] is False
    assert result["commercial_owner_go"] is False
    assert result["automatic_submission_or_payment"] is False
    assert not any(key in result for key in SAMPLE)
    assert Decimal(result["cash_break_even_rub"]) < Decimal(result["full_economic_break_even_rub"])


@pytest.mark.parametrize("key", list(SAMPLE))
def test_every_user_cost_assumption_is_required(key):
    without = {k: v for k, v in SAMPLE.items() if k != key}
    with pytest.raises(ValidationError):
        ExplicitCostScenarioRequest(**without)


def test_extra_fields_and_false_explicit_acknowledgment_rejected():
    with pytest.raises(ValidationError):
        ExplicitCostScenarioRequest(**{**SAMPLE, "unexpected": "field"})
    with pytest.raises(HTTPException) as exc:
        calculate_explicit_cost_thresholds(
            ExplicitCostScenarioRequest(**{**SAMPLE, "accept_hypothetical_assumptions_only": False})
        )
    assert exc.value.status_code == 422


def test_zero_expenses_is_not_a_viable_commercial_scenario():
    values = {**SAMPLE, **{
        key: "0" for key in (
            "external_direct_rub", "labor_rub", "reserve_rub",
            "fixed_platform_fees_rub",
        )
    }}
    with pytest.raises(HTTPException) as exc:
        calculate_explicit_cost_thresholds(ExplicitCostScenarioRequest(**values))
    assert exc.value.status_code == 422


def test_labor_only_cost_is_valid_even_with_zero_cash_outlays():
    """Explicit owner labor is a real economic cost; no external fee is required."""
    values = {
        **SAMPLE,
        "external_direct_rub": "0",
        "reserve_rub": "0",
        "fixed_platform_fees_rub": "0",
        "labor_rub": "200",
        "revenue_tax_percent": "0",
        "variable_platform_fee_percent": "0",
        "target_profit_rub": "0",
    }
    result = calculate_explicit_cost_thresholds(ExplicitCostScenarioRequest(**values))
    assert result["cash_break_even_rub"] == "0.00"
    assert result["full_economic_break_even_rub"] == "200.00"
    assert result["full_cost_plus_explicit_target_rub"] == "200.00"
    assert result["is_procurement_bid_recommendation"] is False


def test_zero_explicit_labor_stays_hypothetical_not_a_bid():
    values = {**SAMPLE, "labor_rub": "0", "target_profit_rub": "0"}
    result = calculate_explicit_cost_thresholds(ExplicitCostScenarioRequest(**values))
    assert result["cash_break_even_rub"] == result["full_economic_break_even_rub"]
    assert result["full_economic_break_even_rub"] == result["full_cost_plus_explicit_target_rub"]
    assert result["is_procurement_bid_recommendation"] is False


@pytest.mark.parametrize(("field", "value"), [
    ("external_direct_rub", "-1"),
    ("external_direct_rub", "10.999"),
    ("labor_rub", "1e20"),
    ("reserve_rub", "1,00"),
    ("target_profit_rub", ""),
    ("revenue_tax_percent", "-6"),
    ("revenue_tax_percent", "0.12345"),
    ("revenue_tax_percent", "1000"),
    ("variable_platform_fee_percent", "1e3"),
])
def test_invalid_user_monetary_or_percentage_shapes(field, value):
    with pytest.raises(ValidationError):
        ExplicitCostScenarioRequest(**{**SAMPLE, field: value})


@pytest.mark.parametrize("rates", [
    {"revenue_tax_percent": "100", "variable_platform_fee_percent": "0"},
    {"revenue_tax_percent": "60", "variable_platform_fee_percent": "40"},
    {"revenue_tax_percent": "99.9999", "variable_platform_fee_percent": "0.0001"},
])
def test_rates_consuming_entire_revenue_rejected(rates):
    with pytest.raises(HTTPException) as exc:
        calculate_explicit_cost_thresholds(ExplicitCostScenarioRequest(**{**SAMPLE, **rates}))
    assert exc.value.status_code == 422


def test_near_one_hundred_percent_rate_keeps_exact_decimal_result():
    result = calculate_explicit_cost_thresholds(
        ExplicitCostScenarioRequest(**{
            **SAMPLE,
            "revenue_tax_percent": "99.9999",
            "variable_platform_fee_percent": "0",
        })
    )
    assert Decimal(result["full_economic_break_even_rub"]) > Decimal(10000000)
    assert result["is_procurement_bid_recommendation"] is False
