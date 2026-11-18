"""Explicit dated cash scenario, reconciled to PRICE01; no actual cash claims."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .operator_cost_scenarios import (
    ExplicitCostScenarioRequest,
    calculate_explicit_cost_thresholds,
)

Category = Literal[
    'advance', 'stage_payment', 'final_payment', 'external_direct', 'labor_cash',
    'reserve', 'fixed_platform_fee', 'guarantee_fee', 'revenue_tax',
    'variable_platform_fee', 'bid_security_hold', 'bid_security_return',
    'contract_security_hold', 'contract_security_return',
]
_RECEIPTS = frozenset({'advance', 'stage_payment', 'final_payment'})
_RETURNS = frozenset({'bid_security_return', 'contract_security_return'})
_IN = _RECEIPTS | _RETURNS
_MONEY = r'^\d{1,12}(?:\.\d{1,2})?$'
_DATE = r'^\d{4}-\d{2}-\d{2}$'


class CashEvent(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    event_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    event_date: str = Field(pattern=_DATE)
    stage: str = Field(min_length=1, max_length=100)
    category: Category
    amount_rub: str = Field(pattern=_MONEY, max_length=15)


class CashCalendarRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start_date: str = Field(pattern=_DATE)
    end_date: str = Field(pattern=_DATE)
    opening_available_cash_rub: str = Field(pattern=_MONEY, max_length=15)
    labor_cash_rub: str = Field(pattern=_MONEY, max_length=15)
    events: list[CashEvent] = Field(min_length=1, max_length=256)
    receipt_delay_calendar_days: list[StrictInt] = Field(max_length=8)
    accept_hypothetical_assumptions_only: Literal[True]


def _cents(value):
    return int(Decimal(value)*100)


def _rub(value):
    return format(Decimal(value)/100,'.2f')


def _one_scenario(events, start, end, opening, delay):
    dated=defaultdict(list)
    for event in events:
        day=date.fromisoformat(event.event_date)
        if event.category in _RECEIPTS:
            day+=timedelta(days=delay)
        dated[day].append(event)
    end=max(end,max(dated))
    if (end-start).days>1095:
        raise ValueError('Scenario horizon too long')
    balance=0
    peak=0
    peak_day=start
    deficit_days=0
    day=start
    rows=[]
    held={'bid':0,'contract':0}
    while day<=end:
        outgoing=incoming=0
        # Conservative same-day ordering: all outflows before inflows.
        for e in sorted(dated.get(day,[]),key=lambda e:(e.category in _IN,e.event_id)):
            value=_cents(e.amount_rub)
            c=e.category
            for kind in ("bid","contract"):
                if c==kind+'_security_hold':
                    held[kind]+=value
                elif c==kind+'_security_return':
                    held[kind]-=value
                    if held[kind]<0:
                        raise ValueError('Security returned before it was held')
            if c in _IN:
                incoming+=value
            else:
                outgoing+=value
        trough=balance-outgoing
        if -trough>peak:
            peak=-trough
            peak_day=day
        balance=trough+incoming
        deficit_days+=opening+balance<0
        rows.append({'date':day.isoformat(),'outflow_rub':_rub(outgoing),'inflow_rub':_rub(incoming),
                     'intraday_minimum_before_opening_cash_rub':_rub(trough),
                     'closing_net_cash_rub':_rub(balance),'closing_after_opening_cash_rub':_rub(opening+balance),
                     'security_locked_at_close_rub':_rub(sum(held.values())),
                     'event_ids':[e.event_id for e in dated.get(day,[])]})
        day+=timedelta(days=1)
    if any(held.values()):
        raise ValueError('Security not fully returned in scenario horizon')
    return {'receipt_delay_calendar_days':delay,'peak_funding_required_rub':_rub(peak),
            'peak_date':peak_day.isoformat() if peak else None,
            'additional_funding_needed_rub':_rub(max(0,peak-opening)),
            'days_with_negative_closing_after_opening_cash':deficit_days,
            'ending_net_cash_rub':_rub(balance),'ending_after_opening_cash_rub':_rub(opening+balance),
            'daily_balances':rows}


def calculate_cash_calendar(cost: ExplicitCostScenarioRequest, calendar: CashCalendarRequest) -> dict:
    """Full explicit calendar only. No default dates, tax or source interpretation."""
    price=calculate_explicit_cost_thresholds(cost)
    offer=cost.offer_scenario
    if offer is None:
        raise ValueError('Explicit offer scenario required')
    opening=_cents(calendar.opening_available_cash_rub)
    labor=_cents(calendar.labor_cash_rub)
    if labor>_cents(cost.labor_rub):
        raise ValueError('Cash labor cannot exceed economic labor')
    start,end=map(date.fromisoformat,(calendar.start_date,calendar.end_date))
    if not date(2000,1,1)<=start<=end<=date(2100,1,1) or (end-start).days>730:
        raise ValueError('Invalid explicit calendar horizon')
    delays=calendar.receipt_delay_calendar_days
    if len(set(delays))!=len(delays) or any(not 1<=x<=365 for x in delays):
        raise ValueError('Stress delays must be distinct positive days <=365')
    totals=defaultdict(int)
    ids=set()
    for e in calendar.events:
        if e.event_id in ids or not start<=date.fromisoformat(e.event_date)<=end or _cents(e.amount_rub)<=0:
            raise ValueError('Duplicate, zero, or outside-horizon event')
        ids.add(e.event_id)
        totals[e.category]+=_cents(e.amount_rub)
    p=price['offer_scenario']
    expected={'external_direct':_cents(cost.external_direct_rub),'labor_cash':labor,
              'reserve':_cents(cost.reserve_rub),'fixed_platform_fee':_cents(cost.fixed_platform_fees_rub),
              'guarantee_fee':_cents(offer.nonrefundable_guarantee_fees_rub),
              'revenue_tax':_cents(p['modeled_revenue_tax_rub']),
              'variable_platform_fee':_cents(p['modeled_variable_fee_rub']),
              'bid_security_hold':_cents(offer.refundable_bid_cash_rub),
              'bid_security_return':_cents(offer.refundable_bid_cash_rub),
              'contract_security_hold':_cents(offer.refundable_contract_cash_rub),
              'contract_security_return':_cents(offer.refundable_contract_cash_rub)}
    if any(totals[k]!=v for k,v in expected.items()) or sum(totals[k] for k in _RECEIPTS)!=_cents(offer.offer_price_rub):
        raise ValueError('Calendar amounts differ from PRICE01 assumptions')
    net=_cents(offer.offer_price_rub)-sum(v for k,v in expected.items() if k not in _RETURNS and not k.endswith('_hold'))
    cases=[_one_scenario(calendar.events,start,end,opening,d) for d in [0,*sorted(delays)]]
    if any(_cents(c['ending_net_cash_rub'])!=net for c in cases):
        raise ValueError('Scenario net reconciliation failed')
    worst=max(cases,key=lambda c:_cents(c['peak_funding_required_rub']))
    return {'status':'EXPLICIT_DATED_CASH_SCENARIO_ONLY','currency':'RUB',
            'opening_cash_assumption_rub':_rub(opening),'economic_profit_rub':p['economic_profit_rub'],
            'labor_cash_assumption_rub':_rub(labor),'labor_non_cash_assumption_rub':_rub(_cents(cost.labor_rub)-labor),
            'scenario_net_cash_rub':_rub(net),'all_modeled_cost_categories_reconciled':True,
            'same_day_order':'OUTFLOWS_BEFORE_INFLOWS','stress_policy':'SHIFT_ALL_CUSTOMER_RECEIPTS_ONLY',
            'security_return_assumptions_unchanged_in_stress':True,'tax_fee_assumptions_unchanged_in_stress':True,
            'worst_modeled_peak_funding_rub':worst['peak_funding_required_rub'],
            'worst_modeled_additional_funding_rub':worst['additional_funding_needed_rub'],
            'cases':cases,'actual_peak_working_capital_rub':None,'actual_cash_gap_days':None,
            'actual_payment_dates_verified':False,'current_security_verified':False,
            'whole_financial_plan_verified':False,'go_eligible':False,'external_action_allowed':False}
