from copy import deepcopy

import pytest
from pydantic import ValidationError

from scripts.acceptance.apr03b_cash_calendar_fixture import calendar_fixture
from src.modules.tender_operator_agent_demo.operator_cashflow_calendar import (
    CashCalendarRequest,
    calculate_cash_calendar,
)
from src.modules.tender_operator_agent_demo.operator_cost_scenarios import (
    ExplicitCostScenarioRequest,
)


def cost():
    return ExplicitCostScenarioRequest(external_direct_rub='250000',labor_rub='300000',
        reserve_rub='50000',fixed_platform_fees_rub='10000',revenue_tax_percent='6',
        variable_platform_fee_percent='1',target_profit_rub='100000',
        offer_scenario={'offer_price_rub':'900000','nonrefundable_guarantee_fees_rub':'5000',
                        'refundable_bid_cash_rub':'20000','refundable_contract_cash_rub':'100000'},
        accept_hypothetical_assumptions_only=True)


def test_reconciled_cash_schedule():
    out=calculate_cash_calendar(cost(),calendar_fixture())
    assert out['scenario_net_cash_rub']=='372000.00'
    assert out['economic_profit_rub']=='222000.00'
    assert out['labor_non_cash_assumption_rub']=='150000.00'
    assert [c['peak_funding_required_rub'] for c in out['cases']]==['285000.00','515000.00','628000.00']
    assert [c['additional_funding_needed_rub'] for c in out['cases']]==['85000.00','315000.00','428000.00']
    assert [c['peak_date'] for c in out['cases']]==['2027-01-03','2027-01-10','2027-01-21']
    assert all(c['ending_net_cash_rub']=='372000.00' for c in out['cases'])
    assert all(c['daily_balances'][-1]['security_locked_at_close_rub']=='0.00' for c in out['cases'])
    assert not out['go_eligible'] and out['actual_peak_working_capital_rub'] is None


@pytest.mark.parametrize('change',['missing','duplicate','amount','tax','early_return','wrong_labor',
                                  'outside','invalid_date','zero','delay_duplicate','delay_zero','long_horizon'])
def test_reject_invalid_reconciliations(change):
    d=deepcopy(calendar_fixture().model_dump())
    es=d['events']
    if change=='missing':es.pop(3)
    elif change=='duplicate':es[1]['event_id']=es[0]['event_id']
    elif change=='amount':es[6]['amount_rub']='269999.99'
    elif change=='tax':es[13]['amount_rub']='53999.99'
    elif change=='early_return':es[-1]['event_date']='2027-01-01'
    elif change=='wrong_labor':d['labor_cash_rub']='300001'
    elif change=='outside':es[3]['event_date']='2027-01-26'
    elif change=='invalid_date':es[3]['event_date']='2027-02-30'
    elif change=='zero':es[2]['amount_rub']='0'
    elif change=='delay_duplicate':d['receipt_delay_calendar_days']=[7,7]
    elif change=='delay_zero':d['receipt_delay_calendar_days']=[0]
    elif change=='long_horizon':d['end_date']='2030-01-01'
    with pytest.raises(ValueError):
        calculate_cash_calendar(cost(),CashCalendarRequest.model_validate(d))


def test_same_day_outflow_before_inflow():
    d=calendar_fixture().model_dump()
    d['events'][6]['event_date']='2027-01-03'
    result=calculate_cash_calendar(cost(),CashCalendarRequest.model_validate(d))
    assert result['cases'][0]['peak_funding_required_rub']=='285000.00'
    day=result['cases'][0]['daily_balances'][2]
    assert day['closing_net_cash_rub']=='-15000.00'
    assert day['intraday_minimum_before_opening_cash_rub']=='-285000.00'


def test_missing_offer_and_strict_delay():
    d=cost().model_dump();d['offer_scenario']=None
    with pytest.raises(ValueError,match='offer'):
        calculate_cash_calendar(ExplicitCostScenarioRequest.model_validate(d),calendar_fixture())
    d=calendar_fixture().model_dump();d['receipt_delay_calendar_days']=[True]
    with pytest.raises(ValidationError):
        CashCalendarRequest.model_validate(d)


def test_local_cli_explicit_schedule(monkeypatch,tmp_path,capsys):
    from scripts.acceptance import review_ri223_archived_owner as cli

    p=tmp_path/'price.json';p.write_text(cost().model_dump_json())
    q=tmp_path/'calendar.json';q.write_text(calendar_fixture().model_dump_json())
    def review(run,scenario,*,include_decision,cash_calendar):
        assert run=='test' and include_decision
        return calculate_cash_calendar(scenario,cash_calendar)
    monkeypatch.setattr(cli,'review_archived_owner_run',review)
    monkeypatch.setattr('sys.argv',['review','--run-id','test','--scenario-json',str(p),
                                   '--cash-calendar-json',str(q),'--decision'])
    cli.main()
    assert '"worst_modeled_peak_funding_rub": "628000.00"' in capsys.readouterr().out
    monkeypatch.setattr('sys.argv',['review','--run-id','test','--cash-calendar-json',str(q)])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code==2
