"""Explicit synthetic costs and dates, not observed payments."""
from calendar import monthrange
from datetime import date, timedelta

from src.modules.tender_operator_agent_demo.operator_cost_scenarios import (
    ExplicitCostScenarioRequest,
)
from src.modules.tender_operator_agent_demo.ri223_staged_calendar import StagedRequest


def inputs():
    cost=ExplicitCostScenarioRequest(external_direct_rub='72000',labor_rub='24000',reserve_rub='0',
        fixed_platform_fees_rub='0',revenue_tax_percent='6',variable_platform_fee_percent='0',target_profit_rub='10000',
        offer_scenario={'offer_price_rub':'143640','nonrefundable_guarantee_fees_rub':'0',
                         'refundable_bid_cash_rub':'0','refundable_contract_cash_rub':'0'},
        accept_hypothetical_assumptions_only=True)
    start=date(2026,10,1);end=date(2027,11,30)
    rows=[];months=[]
    for i in range(12):
        y,m=divmod(2026*12+9+i,12);m+=1
        first=date(y,m,1);last=date(y,m,monthrange(y,m)[1]);invoice=last+timedelta(days=3)
        for category,amt in [('external_direct','6000'),('labor_cash','1000')]:
            rows.append({'event_id':f'{category}_{i}','event_date':first.isoformat(),'stage':first.isoformat(),'category':category,'amount_rub':amt})
        months.append({'period_end':last.isoformat(),'invoice_issued':invoice.isoformat(),
                       'accepted_date':invoice.isoformat(),'payment_documents_received':invoice.isoformat(),'amount_rub':'11970'})
    rows.append({'event_id':'tax','event_date':'2027-10-31','stage':'synthetic tax','category':'revenue_tax','amount_rub':'8618.40'})
    req=StagedRequest(ledger_without_customer_receipts={'start_date':start.isoformat(),'end_date':end.isoformat(),
        'opening_available_cash_rub':'10000','labor_cash_rub':'12000','events':rows,
        'receipt_delay_calendar_days':[7,30],'accept_hypothetical_assumptions_only':True},
        work_calendar={'coverage_start':start.isoformat(),'coverage_end':end.isoformat(),
                       'working_dates':[(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1) if (start+timedelta(days=i)).weekday()<5],
                       'accept_complete_workday_list_as_assumption':True},
        mode='monthly',monthly=months,assume_customer_elected_full_advance=False,
        assume_draft_annex_controls_for_scenario=True,assume_all_payment_documents_and_acceptance_complete=True,
        assume_explicit_tax_and_full_period_amounts=True,bank_credit_lag_days=0)
    return cost,req


def advance(req):
    return StagedRequest.model_validate({**req.model_dump(),'mode':'discretionary_full_advance','monthly':[],
        'assume_customer_elected_full_advance':True,'advance_invoice_date':'2026-10-01','assumed_advance_credit_date':'2026-10-02'})


def replay_staged(run_id):
    from src.modules.tender_operator_agent_demo.ri223_staged_calendar import _compute
    from src.modules.tender_operator_agent_demo.ri223_staged_evidence import (
        observe_staged_terms,
    )
    cost,req=inputs()
    terms=observe_staged_terms(run_id)
    print('RI223_STAGED_TERMS',terms['status'],{k:list(v) for k,v in terms.get('source_groups',{}).items()},flush=True)
    assert terms['complete_reviewed_groups'],terms['status']
    a=_compute(cost,terms,req);b=_compute(cost,terms,advance(req))
    assert len(a['generated_events'])==12 and len(b['generated_events'])==1
    assert a['cash_calendar']['scenario_net_cash_rub']==b['cash_calendar']['scenario_net_cash_rub']=='51021.60'
    assert not a['go_eligible'] and not b['advance_guaranteed']
    print('RI223_STAGED_CALENDAR_PASS',[(p['mode'],[(c['receipt_delay_calendar_days'],c['peak_funding_required_rub']) for c in p['cash_calendar']['cases']]) for p in (a,b)],flush=True)


def replay_withholding(run_id):
    from scripts.acceptance.apr03b_cash_calendar_fixture import calendar_fixture
    from src.modules.tender_operator_agent_demo.ri223_staged_calendar import (
        withholding_stress,
    )

    cost=ExplicitCostScenarioRequest(external_direct_rub='250000',labor_rub='300000',reserve_rub='50000',
        fixed_platform_fees_rub='10000',revenue_tax_percent='6',variable_platform_fee_percent='1',target_profit_rub='100000',
        offer_scenario={'offer_price_rub':'900000','nonrefundable_guarantee_fees_rub':'5000',
                        'refundable_bid_cash_rub':'20000','refundable_contract_cash_rub':'100000'},
        accept_hypothetical_assumptions_only=True)
    out=withholding_stress(run_id,cost,calendar_fixture(),'e06','100000')
    print('RI223_WITHHOLDING_ACTUAL',out['status'],flush=True)
    assert out['status']=='HYPOTHETICAL_UNRECOVERED_WITHHOLDING_ONLY',out
    assert out['net_cash_after_assumed_nonreceipt_rub']=='272000.00' and out['refund_date'] is None
    print('RI223_WITHHOLDING_PASS',[(c['receipt_delay_calendar_days'],c['peak_funding_required_rub']) for c in out['cases']],flush=True)
