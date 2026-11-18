"""Conditional settlement dates from the exact reviewed archived draft."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from .operator_cashflow_calendar import (
    CashCalendarRequest,
    CashEvent,
    calculate_cash_calendar,
)
from .ri223_linked_contract import _PARAGRAPHS, _SOURCE_SHA

_DATE = r'^\d{4}-\d{2}-\d{2}$'


class ExplicitWorkCalendar(BaseModel):
    model_config = ConfigDict(extra='forbid')
    coverage_start: str = Field(pattern=_DATE)
    coverage_end: str = Field(pattern=_DATE)
    working_dates: list[Annotated[str, Field(pattern=_DATE)]] = Field(min_length=1,max_length=731)
    accept_complete_workday_list_as_assumption: StrictBool


class ContractPaymentCalendarRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ledger_without_customer_receipts: CashCalendarRequest
    work_calendar: ExplicitWorkCalendar
    act_received_date: str = Field(pattern=_DATE)
    invoice_and_invoice_facture_provided_by_signing: StrictBool
    assume_no_motivated_refusal: StrictBool
    assume_bank_transfer_without_alternative_agreement: StrictBool
    assume_single_full_settlement: StrictBool
    bank_receipt_lag_calendar_days: StrictInt = Field(ge=0,le=90)


def _supported_group(linked):
    group=linked.get('groups',{}).get('acceptance_payment',{})
    sources=group.get('source_sections',{})
    if (group.get('status')!='VERIFIED_REVIEWED_PARAGRAPH_GROUP'
            or set(sources)!= {'3.4','4.3','4.4'}):
        return False
    identities=set()
    for section,paragraph in sources.items():
        fragments=paragraph.get('fragments',[])
        if (paragraph.get('status')!='FULL_PINNED_PARAGRAPH_PARTS_VERIFIED' or not fragments
                or any(not isinstance(x,dict) or not isinstance(x.get('quote'),str)
                       or x.get('original_sha256')!=_SOURCE_SHA
                       or x.get('ri223_container',{}).get('member_sha256')!=_SOURCE_SHA
                       or not x.get('chunk_id') or not x.get('file_id') for x in fragments)
                or ' '.join(x['quote'] for x in fragments)!=_PARAGRAPHS[section]):
            return False
        identities.update(x['file_id'] for x in fragments)
    return len(identities)==1


def project_payment_calendar(cost, linked, request):
    """Only consumes groups freshly attested inside the owner review."""
    unknown={'status':'UNKNOWN','cash_calendar':None,'actual_receipt_date':None,'go_eligible':False}
    if not _supported_group(linked):
        return {**unknown,'reason':'COMPLETE_VERIFIED_PAYMENT_GROUP_REQUIRED'}
    if not all((request.work_calendar.accept_complete_workday_list_as_assumption,
                request.invoice_and_invoice_facture_provided_by_signing,request.assume_no_motivated_refusal,
                request.assume_bank_transfer_without_alternative_agreement,request.assume_single_full_settlement)):
        return {**unknown,'reason':'EXPLICIT_PAYMENT_CONDITIONS_REQUIRED'}
    if cost.offer_scenario is None:
        raise ValueError('Explicit offer required')
    ledger=request.ledger_without_customer_receipts
    if any(e.category in ('advance','stage_payment','final_payment') for e in ledger.events):
        raise ValueError('Generated payment cannot coexist with manual customer receipts')
    wc=request.work_calendar
    start,end=map(date.fromisoformat,(wc.coverage_start,wc.coverage_end))
    if not date(2000,1,1)<=start<=end<=date(2100,1,1) or (end-start).days>730:
        raise ValueError('Invalid work calendar coverage')
    working=[date.fromisoformat(x) for x in wc.working_dates]
    if len(set(working))!=len(working) or any(not start<=x<=end for x in working):
        raise ValueError('Duplicate or outside-coverage working date')
    active=set(working)
    received=date.fromisoformat(request.act_received_date)
    if not start<=received<=end or not date.fromisoformat(ledger.start_date)<=received<=date.fromisoformat(ledger.end_date):
        raise ValueError('Act reception outside covered ledger/calendar')
    def add_workdays(day,count):
        for _ in range(count):
            day+=timedelta(days=1)
            while day<=end and day not in active:
                day+=timedelta(days=1)
            if day>end:
                raise ValueError('Insufficient explicit work calendar coverage')
        return day
    signed=add_workdays(received,10)
    debit=add_workdays(signed,7)
    receipt=debit+timedelta(days=request.bank_receipt_lag_calendar_days)
    if receipt>date.fromisoformat(ledger.end_date):
        raise ValueError('Projected receipt outside explicit ledger horizon')
    event=CashEvent(event_id='contract_generated_final',event_date=receipt.isoformat(),
                    stage='assumed single settlement',category='final_payment',
                    amount_rub=cost.offer_scenario.offer_price_rub)
    generated=ledger.model_copy(update={'events':[*ledger.events,event]})
    cash=calculate_cash_calendar(cost,CashCalendarRequest.model_validate(generated.model_dump()))
    return {'status':'CONDITIONAL_ARCHIVED_PAYMENT_CALENDAR_ONLY',
            'source_sections':linked['groups']['acceptance_payment']['source_sections'],
            'act_received_assumption_date':received.isoformat(),
            'modeled_signing_date':signed.isoformat(),'modeled_customer_debit_date':debit.isoformat(),
            'modeled_bank_receipt_date':receipt.isoformat(),'bank_lag_assumption_calendar_days':request.bank_receipt_lag_calendar_days,
            'work_calendar_is_explicit_assumption':True,'trigger_day_excluded_by_assumption':True,
            'single_settlement_assumed_not_attested':True,'motivated_refusal_duration_unknown':True,
            'generated_event':event.model_dump(),'cash_calendar':cash,
            'actual_receipt_date':None,'guaranteed_latest_payment_date':None,'legal_calendar_verified':False,
            'current_revision_attested':False,'go_eligible':False,'external_action_allowed':False}
