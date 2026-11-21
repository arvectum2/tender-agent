"""Stateless PRICE-01 what-if calculator. All cost/tax assumptions must be explicit.

No database, request logs, history, bid recommendation, procurement interaction
or implicit user/company tax rates. Uses existing tested Decimal price function.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.tender_research.competitive_bid_protocol import (
    compute_owner_supplied_break_even,
)

_RUB_PATTERN = r"^\d{1,12}(?:\.\d{1,2})?$"
_PERCENT_PATTERN = r"^\d{1,3}(?:\.\d{1,4})?$"


class ExplicitOfferScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offer_price_rub: str = Field(max_length=15, pattern=_RUB_PATTERN)
    nonrefundable_guarantee_fees_rub: str = Field(max_length=15, pattern=_RUB_PATTERN)
    refundable_bid_cash_rub: str = Field(max_length=15, pattern=_RUB_PATTERN)
    refundable_contract_cash_rub: str = Field(max_length=15, pattern=_RUB_PATTERN)


class ExplicitCostScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_direct_rub: str = Field(min_length=1, max_length=15, pattern=_RUB_PATTERN)
    labor_rub: str = Field(min_length=1, max_length=15, pattern=_RUB_PATTERN)
    reserve_rub: str = Field(min_length=1, max_length=15, pattern=_RUB_PATTERN)
    fixed_platform_fees_rub: str = Field(min_length=1, max_length=15, pattern=_RUB_PATTERN)
    revenue_tax_percent: str = Field(min_length=1, max_length=8, pattern=_PERCENT_PATTERN)
    variable_platform_fee_percent: str = Field(min_length=1, max_length=8, pattern=_PERCENT_PATTERN)
    target_profit_rub: str = Field(min_length=1, max_length=15, pattern=_RUB_PATTERN)
    offer_scenario: ExplicitOfferScenario | None = None
    accept_hypothetical_assumptions_only: bool = Field(
        description="Confirm explicit what-if only, not binding commercial GO."
    )


def calculate_explicit_cost_thresholds(request: ExplicitCostScenarioRequest) -> dict:
    """All 7 monetary/rate fields required; no actual Owner proof implied."""
    if request.accept_hypothetical_assumptions_only is not True:
        raise HTTPException(status_code=422, detail="Требуется подтверждение сценарного, а не коммерческого расчёта")
    offer = request.offer_scenario
    guarantee_fee = Decimal(offer.nonrefundable_guarantee_fees_rub) if offer else Decimal(0)
    fixed_fees = Decimal(request.fixed_platform_fees_rub) + guarantee_fee
    if sum((
        Decimal(request.external_direct_rub),
        Decimal(request.labor_rub),
        Decimal(request.reserve_rub),
        fixed_fees,
    )) <= 0:
        raise HTTPException(status_code=422, detail="Укажите хотя бы одну ненулевую статью расходов")
    try:
        result = compute_owner_supplied_break_even(
            external_direct_rub=request.external_direct_rub,
            labor_rub=request.labor_rub,
            reserve_rub=request.reserve_rub,
            fixed_platform_fees_rub=fixed_fees,
            revenue_tax_rate=Decimal(request.revenue_tax_percent) / Decimal(100),
            variable_platform_fee_rate=Decimal(request.variable_platform_fee_percent) / Decimal(100),
            target_profit_rub=request.target_profit_rub,
        )
    except (ValueError, ArithmeticError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Ставки и суммы некорректны либо налог и комиссия съедают всю выручку",
        ) from exc
    packet = {
        "state": "EXPLICIT_USER_ASSUMPTION_BREAK_EVEN_ONLY",
        "currency": "RUB",
        "cash_break_even_rub": result["cash_cost_break_even_rub"],
        "full_economic_break_even_rub": result["full_economic_break_even_rub"],
        "full_cost_plus_explicit_target_rub": result["full_cost_plus_explicit_target_rub"],
        "money_rounded_up_to_kopecks": True,
        "inputs_stored": False,
        "assumptions_independently_verified": False,
        "is_procurement_bid_recommendation": False,
        "probability_of_winning_estimated": False,
        "commercial_owner_go": False,
        "automatic_submission_or_payment": False,
    }

    if offer is not None:
        with localcontext() as context:
            context.prec = 40
            price = Decimal(offer.offer_price_rub)
            if price <= 0:
                raise HTTPException(status_code=422, detail="Цена сценария должна быть больше нуля")
            tax = price * Decimal(request.revenue_tax_percent) / 100
            variable_fee = price * Decimal(request.variable_platform_fee_percent) / 100
            cash_costs = Decimal(request.external_direct_rub) + Decimal(request.reserve_rub) + fixed_fees + tax + variable_fee
            economic_costs = cash_costs + Decimal(request.labor_rub)
            profit = price - economic_costs
            collateral = Decimal(offer.refundable_bid_cash_rub) + Decimal(offer.refundable_contract_cash_rub)
            def money(value: Decimal) -> str:
                return format(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), 'f')
            packet['offer_scenario'] = {
                'kind': 'EXPLICIT_OFFER_AND_PRE_RECEIPT_STRESS_ONLY',
                'offer_price_rub': money(price),
                'modeled_revenue_tax_rub': money(tax),
                'modeled_variable_fee_rub': money(variable_fee),
                'economic_cost_rub': money(economic_costs),
                'economic_profit_rub': money(profit),
                'economic_margin_percent': money(profit / price * 100),
                'cash_cost_rub': money(cash_costs),
                'refundable_cash_collateral_rub': money(collateral),
                'pre_receipt_stress_cash_rub': money(cash_costs + collateral),
                'actual_peak_working_capital_rub': None,
                'actual_security_requirement_rub': None,
                'target_profit_met_in_scenario': profit >= Decimal(request.target_profit_rub),
                'cash_timing_assumption': 'ALL_MODELED_CASH_COSTS_AND_BOTH_REFUNDABLE_DEPOSITS_BEFORE_FIRST_RECEIPT',
                'labor_treated_as_non_cash': True,
                'collateral_treated_as_fully_refundable': True,
                'amounts_display_round_half_up_independently': True,
            }
    return packet
