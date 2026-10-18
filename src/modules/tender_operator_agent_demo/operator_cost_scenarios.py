"""Stateless PRICE-01 what-if calculator. All cost/tax assumptions must be explicit.

No database, request logs, history, bid recommendation, procurement interaction
or implicit user/company tax rates. Uses existing tested Decimal price function.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.tender_research.competitive_bid_protocol import (
    compute_owner_supplied_break_even,
)

_RUB_PATTERN = r"^\d{1,12}(?:\.\d{1,2})?$"
_PERCENT_PATTERN = r"^\d{1,3}(?:\.\d{1,4})?$"


class ExplicitCostScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_direct_rub: str = Field(min_length=1, max_length=15, pattern=_RUB_PATTERN)
    labor_rub: str = Field(min_length=1, max_length=15, pattern=_RUB_PATTERN)
    reserve_rub: str = Field(min_length=1, max_length=15, pattern=_RUB_PATTERN)
    fixed_platform_fees_rub: str = Field(min_length=1, max_length=15, pattern=_RUB_PATTERN)
    revenue_tax_percent: str = Field(min_length=1, max_length=8, pattern=_PERCENT_PATTERN)
    variable_platform_fee_percent: str = Field(min_length=1, max_length=8, pattern=_PERCENT_PATTERN)
    target_profit_rub: str = Field(min_length=1, max_length=15, pattern=_RUB_PATTERN)
    accept_hypothetical_assumptions_only: bool = Field(
        description="Confirm explicit what-if only, not binding commercial GO."
    )


def calculate_explicit_cost_thresholds(request: ExplicitCostScenarioRequest) -> dict:
    """All 7 monetary/rate fields required; no actual Owner proof implied."""
    if request.accept_hypothetical_assumptions_only is not True:
        raise HTTPException(status_code=422, detail="Требуется подтверждение сценарного, а не коммерческого расчёта")
    if sum((
        Decimal(request.external_direct_rub),
        Decimal(request.labor_rub),
        Decimal(request.reserve_rub),
        Decimal(request.fixed_platform_fees_rub),
        Decimal(request.labor_rub),
    )) <= 0:
        raise HTTPException(status_code=422, detail="Укажите хотя бы одну ненулевую статью расходов")
    try:
        result = compute_owner_supplied_break_even(
            external_direct_rub=request.external_direct_rub,
            labor_rub=request.labor_rub,
            reserve_rub=request.reserve_rub,
            fixed_platform_fees_rub=request.fixed_platform_fees_rub,
            revenue_tax_rate=Decimal(request.revenue_tax_percent) / Decimal(100),
            variable_platform_fee_rate=Decimal(request.variable_platform_fee_percent) / Decimal(100),
            target_profit_rub=request.target_profit_rub,
        )
    except (ValueError, ArithmeticError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Ставки и суммы некорректны либо налог и комиссия съедают всю выручку",
        ) from exc
    return {
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
