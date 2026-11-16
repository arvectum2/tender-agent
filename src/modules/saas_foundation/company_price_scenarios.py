"""PRICE-01 scoped scenario economics; not market forecasts or quotes."""
from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal, localcontext
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from src.modules.saas_foundation import company_portfolio as portfolio
from src.modules.saas_foundation.commercial_capture import _authorized
from src.modules.saas_foundation.models import CompanyPriceScenario, SaasMember
from src.modules.saas_foundation.service import audit, legal_required, role_required
from src.tender_research.competitive_bid_protocol import (
    compute_owner_supplied_break_even,
)

Money = Annotated[str, Field(pattern=r'^[0-9]{1,12}(\.[0-9]{1,2})?$',max_length=15)]
Percent = Annotated[str, Field(pattern=r'^[0-9]{1,3}(\.[0-9]{1,4})?$',max_length=8)]
CENT=Decimal('0.01')


class ScenarioInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    # Paid labor goes in external/direct or overhead; own labor is incremental economic cost.
    external_direct_rub: Money
    own_labor_rub: Money
    cash_overhead_rub: Money
    reserve_rub: Money
    fixed_platform_fees_rub: Money
    guarantee_financing_cost_rub: Money
    revenue_tax_percent: Percent
    variable_platform_fee_percent: Percent
    minimum_profit_rub: Money
    target_profit_rub: Money
    reference_ceiling_rub: Money | None = None
    manual_bid_prices_rub: list[Money] = Field(max_length=8)
    assumption_note: str = Field(min_length=1,max_length=2000)
    accept_hypothetical_assumptions_only: Literal[True]

    @model_validator(mode='after')
    def validate_economics(self):
        self.assumption_note=self.assumption_note.strip()
        total=sum(Decimal(getattr(self,k)) for k in ('external_direct_rub','own_labor_rub','cash_overhead_rub','reserve_rub','fixed_platform_fees_rub','guarantee_financing_cost_rub'))
        if not self.assumption_note or total<=0:raise ValueError('Explicit nonzero costs and assumption note required')
        if Decimal(self.revenue_tax_percent)+Decimal(self.variable_platform_fee_percent)>=100:raise ValueError('Rates consume all revenue')
        if Decimal(self.minimum_profit_rub)>Decimal(self.target_profit_rub):raise ValueError('Minimum profit exceeds target')
        prices=[Decimal(x) for x in self.manual_bid_prices_rub]
        if any(x<=0 for x in prices) or len(set(prices))!=len(prices):raise ValueError('Positive unique manual prices required')
        if self.reference_ceiling_rub is not None and Decimal(self.reference_ceiling_rub)<=0:raise ValueError('Positive user reference ceiling required')
        return self


class SaveInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=0,le=30)
    idempotency_key: str = Field(min_length=8,max_length=128)
    scenario: ScenarioInput


def calculate(payload: ScenarioInput) -> dict:
    with localcontext() as context:
        context.prec=40
        def d(name):
            return Decimal(getattr(payload,name))
        external=d('external_direct_rub')+d('cash_overhead_rub')+d('guarantee_financing_cost_rub')
        fixed=external+d('reserve_rub')+d('fixed_platform_fees_rub');labor=d('own_labor_rub')
        tax=d('revenue_tax_percent')/100;fee=d('variable_platform_fee_percent')/100
        divisor=1-tax-fee
        minimum=d('minimum_profit_rub');target=d('target_profit_rub')
        inputs={'external_direct_rub':external,'labor_rub':labor,'reserve_rub':d('reserve_rub'),'fixed_platform_fees_rub':d('fixed_platform_fees_rub'),'revenue_tax_rate':tax,'variable_platform_fee_rate':fee}
        thresholds=compute_owner_supplied_break_even(**inputs,target_profit_rub=target)
        strategic=compute_owner_supplied_break_even(**inputs,target_profit_rub=minimum)['full_cost_plus_explicit_target_rub']
        ceiling=Decimal(payload.reference_ceiling_rub) if payload.reference_ceiling_rub else None
        def evaluate(price,kind):
            p=Decimal(price);cash=p*divisor-fixed;profit=cash-labor
            return {'kind':kind,'price_rub':str(p.quantize(CENT)),'cash_surplus_rub':str(cash.quantize(CENT,rounding=ROUND_FLOOR)),
                    'economic_profit_rub':str(profit.quantize(CENT,rounding=ROUND_FLOOR)),
                    'economic_margin_percent':str((profit/p*100).quantize(Decimal('0.0001'),rounding=ROUND_FLOOR)) if p else None,
                    'cash_break_even_met':cash>=0,'full_break_even_met':profit>=0,'minimum_profit_met':profit>=minimum,'target_profit_met':profit>=target,
                    'within_user_reference_ceiling':p<=ceiling if ceiling is not None else None}
        options=[evaluate(thresholds['cash_cost_break_even_rub'],'CASH_BREAK_EVEN'),evaluate(thresholds['full_economic_break_even_rub'],'FULL_BREAK_EVEN'),evaluate(strategic,'STRATEGIC_MINIMUM_PROFIT'),evaluate(thresholds['full_cost_plus_explicit_target_rub'],'COMMERCIAL_TARGET_PROFIT')]
        options += [evaluate(p,'MANUAL_PRICE') for p in payload.manual_bid_prices_rub]
        return {'schema':'company_price_scenario_v1','currency':'RUB','cash_fixed_and_reserved_rub':str(fixed.quantize(CENT)),'own_labor_rub':str(labor.quantize(CENT)),'full_economic_cost_before_revenue_rates_rub':str((fixed+labor).quantize(CENT)),
                'revenue_retention_rate':str(divisor),'thresholds_rounded_up_to_kopecks':True,'profits_rounded_down_to_kopecks':True,'scenarios':options,
                'reference_ceiling_user_supplied':ceiling is not None,'assumptions_independently_verified':False,'tax_model_verified':False,'market_comparables_used':False,'probability_of_winning_estimated':False,'is_procurement_bid_recommendation':False,'commercial_owner_go':False,'external_submission_allowed':False}


def _query(principal,case_id):
    return select(CompanyPriceScenario).where(CompanyPriceScenario.tenant_id==principal.tenant_id,CompanyPriceScenario.case_id==case_id)


def _view(principal,row):
    try:result=calculate(ScenarioInput.model_validate(row.input_json))
    except (ValueError,ArithmeticError) as exc:raise HTTPException(409,'Stored scenario inputs invalid') from exc
    if result!=row.result_json:raise HTTPException(409,'Stored scenario calculation mismatch')
    return {'customer_id':principal.customer_id,'case_id':row.case_id,'scenario_id':row.id,'revision':row.revision,'member_id':row.member_id,'created_at':portfolio._utc(row.created_at),'inputs':row.input_json,'result':result,'origin':'EXPLICIT_USER_ASSUMPTIONS','external_submission_allowed':False}


def preview(session,principal,case_id,payload):
    legal_required(session,principal);portfolio._owned_case(session,principal,case_id);_authorized(session,principal)
    return {'customer_id':principal.customer_id,'case_id':case_id,'inputs_stored':False,'result':calculate(payload)}


def history(session,principal,case_id,offset=0,limit=10):
    legal_required(session,principal);portfolio._owned_case(session,principal,case_id);_authorized(session,principal)
    rows=list(session.scalars(_query(principal,case_id).order_by(CompanyPriceScenario.revision.desc()).offset(offset).limit(limit+1)))
    return {'customer_id':principal.customer_id,'case_id':case_id,'items':[_view(principal,row) for row in rows[:limit]],'has_more':len(rows)>limit,'external_submission_allowed':False}


def save(session,principal,case_id,payload):
    role_required(principal,'owner','admin');legal_required(session,principal);portfolio._owned_case(session,principal,case_id,lock=True);_authorized(session,principal)
    member=session.get(SaasMember,principal.member_id,populate_existing=True)
    if not member or member.role not in {'owner','admin'}:raise HTTPException(403,'Current manager permission required')
    body=payload.scenario.model_dump(mode='json');query=_query(principal,case_id)
    prior=session.scalar(query.where(CompanyPriceScenario.idempotency_key==payload.idempotency_key))
    if prior:
        if prior.member_id!=principal.member_id or prior.input_json!=body or prior.revision!=payload.expected_revision+1:raise HTTPException(409,'Conflicting scenario replay')
        return _view(principal,prior)
    latest=session.scalar(query.order_by(CompanyPriceScenario.revision.desc()).limit(1))
    revision=latest.revision if latest else 0
    if revision!=payload.expected_revision:raise HTTPException(409,'Scenario revision changed; refresh')
    if revision>=30:raise HTTPException(429,'Scenario revision limit reached')
    row=CompanyPriceScenario(case_id=case_id,tenant_id=principal.tenant_id,member_id=principal.member_id,revision=revision+1,idempotency_key=payload.idempotency_key,input_json=body,result_json=calculate(payload.scenario))
    session.add(row);session.flush();audit(session,principal.tenant_id,'company_price_scenario_saved',principal.member_id,detail=row.id);session.commit()
    return _view(principal,row)
