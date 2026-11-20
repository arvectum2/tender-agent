"""Conditional monthly and discretionary full advance cases."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from .operator_cashflow_calendar import (
    CashCalendarRequest,
    CashEvent,
    _cents,
    _one_scenario,
    _rub,
    calculate_cash_calendar,
)
from .ri223_payment_calendar import ExplicitWorkCalendar
from .ri223_staged_evidence import observe_staged_terms

_DATE=r'^\d{4}-\d{2}-\d{2}$'
_MONEY=r'^\d{1,12}(?:\.\d{1,2})?$'


class MonthlySettlement(BaseModel):
    model_config=ConfigDict(extra='forbid')
    period_end: str=Field(pattern=_DATE)
    invoice_issued: str=Field(pattern=_DATE)
    payment_documents_received: str=Field(pattern=_DATE)
    accepted_date: str=Field(pattern=_DATE)
    amount_rub: str=Field(pattern=_MONEY)


class StagedRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    ledger_without_customer_receipts: CashCalendarRequest
    work_calendar: ExplicitWorkCalendar
    mode: Literal['monthly','discretionary_full_advance']
    monthly: list[MonthlySettlement]=Field(max_length=24)
    advance_invoice_date: str | None=None
    assumed_advance_credit_date: str | None=None
    assume_customer_elected_full_advance: StrictBool
    assume_draft_annex_controls_for_scenario: StrictBool
    assume_all_payment_documents_and_acceptance_complete: StrictBool
    assume_explicit_tax_and_full_period_amounts: StrictBool
    bank_credit_lag_days: StrictInt=Field(ge=0,le=90)


def _compute(cost, terms, request):
    unknown={'status':'UNKNOWN','cash_calendar':None,'actual_payment_dates':None,'go_eligible':False}
    if terms.get('procurement_id')!='32616445632' or not terms.get('complete_reviewed_groups'):
        return {**unknown,'reason':'COMPLETE_REVIEWED_DRAFT_AND_NOTICE_REQUIRED'}
    if not all((request.assume_draft_annex_controls_for_scenario,
                request.assume_all_payment_documents_and_acceptance_complete,
                request.assume_explicit_tax_and_full_period_amounts,
                request.work_calendar.accept_complete_workday_list_as_assumption)):
        return {**unknown,'reason':'EXPLICIT_UNRESOLVED_CONDITIONS_REQUIRED'}
    if cost.offer_scenario is None:
        raise ValueError('Explicit offer required')
    ledger=request.ledger_without_customer_receipts
    if any(e.category in ('advance','stage_payment','final_payment') for e in ledger.events):
        raise ValueError('Manual receipt duplicates generated settlement')
    start,end=map(date.fromisoformat,(ledger.start_date,ledger.end_date))
    wc=request.work_calendar
    ws,we=map(date.fromisoformat,(wc.coverage_start,wc.coverage_end))
    days=[date.fromisoformat(d) for d in wc.working_dates]
    if not date(2000,1,1)<=ws<=we<=date(2100,1,1) or (we-ws).days>730 or len(set(days))!=len(days) or any(not ws<=d<=we for d in days):
        raise ValueError('Invalid work calendar')
    working=set(days)
    events=[]
    projections=[]
    if request.mode=='monthly':
        if not request.monthly or request.advance_invoice_date is not None or request.assumed_advance_credit_date is not None or request.assume_customer_elected_full_advance:
            raise ValueError('Monthly and full advance scenarios are exclusive')
        prior=None
        for i,m in enumerate(request.monthly):
            period,issued,received,accepted=map(date.fromisoformat,(m.period_end,m.invoice_issued,m.payment_documents_received,m.accepted_date))
            if period.day!=monthrange(period.year,period.month)[1] or (prior is not None and period.replace(day=1)!=prior+timedelta(days=1)):
                raise ValueError('Require consecutive full-month assumptions')
            if not start<=period<issued<=period+timedelta(days=5) or not issued<=received or not period<=accepted<=received:
                raise ValueError('Invoice deadline or acceptance/document chronology inconsistent')
            if not ws<=received<=we:
                raise ValueError('Receipt outside work calendar')
            debit=received
            for _ in range(7):
                debit+=timedelta(days=1)
                while debit<=we and debit not in working:
                    debit+=timedelta(days=1)
                if debit>we:
                    raise ValueError('Insufficient work calendar')
            credit=debit+timedelta(days=request.bank_credit_lag_days)
            event=CashEvent(event_id=f'generated_month_{i+1}',event_date=credit.isoformat(),stage=period.isoformat(),
                            category='stage_payment',amount_rub=m.amount_rub)
            events.append(event)
            projections.append({'period_end':period.isoformat(),'modeled_debit_date':debit.isoformat(),'modeled_credit_date':credit.isoformat()})
            prior=period
    else:
        if request.monthly or not request.assume_customer_elected_full_advance or not request.advance_invoice_date or not request.assumed_advance_credit_date:
            return {**unknown,'reason':'CUSTOMER_ELECTION_AND_EXPLICIT_ADVANCE_DATE_REQUIRED'}
        invoice,credit=map(date.fromisoformat,(request.advance_invoice_date,request.assumed_advance_credit_date))
        if not start<=invoice<=credit<=end:
            raise ValueError('Invalid explicit advance chronology')
        events=[CashEvent(event_id='generated_full_advance',event_date=credit.isoformat(),stage='assumed elected advance',
                          category='advance',amount_rub=cost.offer_scenario.offer_price_rub)]
        projections=[{'modeled_credit_date':credit.isoformat(),'contract_deadline_attested':False}]
    generated=CashCalendarRequest.model_validate({**ledger.model_dump(),'events':[*ledger.model_dump()['events'],*[e.model_dump() for e in events]]})
    cash=calculate_cash_calendar(cost,generated)
    return {'status':'CONDITIONAL_STAGED_SETTLEMENT_ONLY','mode':request.mode,'terms':terms,
            'generated_events':[e.model_dump() for e in events],'projections':projections,'cash_calendar':cash,
            'advance_guaranteed':False,'notice_draft_precedence_resolved':False,'vat_recalculated':False,
            'early_termination_or_refusal_modeled':False,'actual_payment_dates':None,'go_eligible':False}


def review_staged_calendar(run_id,cost,request):
    return _compute(cost,observe_staged_terms(run_id),request)


def withholding_stress(run_id,cost,calendar,withheld_event_id,amount_rub):
    terms=observe_staged_terms(run_id)
    if terms.get('procurement_id')!='32616445795' or not terms.get('complete_reviewed_groups'):
        return {'status':'UNKNOWN','reason':'COMPLETE_REVIEWED_TAX_LOSS_CLAUSE_REQUIRED'}
    return _withholding_stress(cost,calendar,withheld_event_id,amount_rub,terms)


def _withholding_stress(cost,calendar,withheld_event_id,amount_rub,terms):
    base=calculate_cash_calendar(cost,calendar)
    amount=Decimal(amount_rub)
    if not amount.is_finite() or not 0<amount<=Decimal('999999999999.99') or amount!=amount.quantize(Decimal('.01')):
        raise ValueError('Invalid assumed withheld amount')
    matches=[e for e in calendar.events if e.event_id==withheld_event_id and e.category in ('advance','stage_payment','final_payment')]
    if len(matches)!=1 or amount>Decimal(matches[0].amount_rub):
        raise ValueError('Withholding exceeds selected receipt')
    target=matches[0]
    residual=Decimal(target.amount_rub)-amount
    events=[e for e in calendar.events if e.event_id!=withheld_event_id]
    if residual:
        events.append(target.model_copy(update={'amount_rub':format(residual,'.2f')}))
    start,end=map(date.fromisoformat,(calendar.start_date,calendar.end_date))
    cases=[_one_scenario(events,start,end,_cents(calendar.opening_available_cash_rub),d)
           for d in [0,*sorted(calendar.receipt_delay_calendar_days)]]
    return {'status':'HYPOTHETICAL_UNRECOVERED_WITHHOLDING_ONLY','terms':terms,'base':base,'cases':cases,
            'withheld_amount_rub':format(amount,'.2f'),'net_cash_after_assumed_nonreceipt_rub':_rub(_cents(base['scenario_net_cash_rub'])-_cents(str(amount))),
            'actual_liability_rub':None,'refund_date':None,'tax_recalculated':False,'go_eligible':False}
