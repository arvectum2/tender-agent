import pytest
from test_apr03b_ri223_linked_contract import review
from test_operator_cashflow_calendar import cost

from scripts.acceptance.apr03b_cash_calendar_fixture import contract_calendar_fixture
from src.modules.tender_operator_agent_demo.ri223_payment_calendar import (
    ContractPaymentCalendarRequest,
    project_payment_calendar,
)


def test_project_dates_and_ledger():
    out=project_payment_calendar(cost(),review(),contract_calendar_fixture())
    assert out['status']=='CONDITIONAL_ARCHIVED_PAYMENT_CALENDAR_ONLY'
    assert out['modeled_signing_date']=='2027-02-03'
    assert out['modeled_customer_debit_date']=='2027-02-12'
    assert out['modeled_bank_receipt_date']=='2027-02-14'
    assert out['generated_event']['amount_rub']=='900000'
    assert all(c['peak_funding_required_rub']=='628000.00' for c in out['cash_calendar']['cases'])
    assert out['cash_calendar']['scenario_net_cash_rub']=='372000.00'
    assert out['actual_receipt_date'] is None and out['guaranteed_latest_payment_date'] is None


@pytest.mark.parametrize('section',['3.4','4.3','4.4'])
def test_missing_source_refuses(section):
    out=project_payment_calendar(cost(),review(missing=(section,)),contract_calendar_fixture())
    assert out['status']=='UNKNOWN' and out['cash_calendar'] is None


@pytest.mark.parametrize('field',['invoice_and_invoice_facture_provided_by_signing','assume_no_motivated_refusal',
                                  'assume_bank_transfer_without_alternative_agreement','assume_single_full_settlement'])
def test_requires_explicit_conditions(field):
    d=contract_calendar_fixture().model_dump();d[field]=False
    out=project_payment_calendar(cost(),review(),ContractPaymentCalendarRequest.model_validate(d))
    assert out['status']=='UNKNOWN' and out['cash_calendar'] is None


@pytest.mark.parametrize('change',['duplicate','outside','coverage','manual','horizon'])
def test_invalid_calendar(change):
    d=contract_calendar_fixture().model_dump();w=d['work_calendar'];l=d['ledger_without_customer_receipts']
    if change=='duplicate':w['working_dates'].append(w['working_dates'][0])
    elif change=='outside':w['working_dates'].append('2027-04-01')
    elif change=='coverage':w['working_dates']=w['working_dates'][:20]
    elif change=='manual':l['events'][0]['category']='advance'
    elif change=='horizon':l['end_date']='2027-02-13'
    with pytest.raises(ValueError):
        project_payment_calendar(cost(),review(),ContractPaymentCalendarRequest.model_validate(d))


def test_workday_override_and_unattested_calendar():
    d=contract_calendar_fixture().model_dump()
    d['work_calendar']['working_dates'].remove('2027-01-21')
    result=project_payment_calendar(cost(),review(),ContractPaymentCalendarRequest.model_validate(d))
    assert result['modeled_signing_date']=='2027-02-04'
    assert result['modeled_customer_debit_date']=='2027-02-15'
    d['work_calendar']['accept_complete_workday_list_as_assumption']=False
    assert project_payment_calendar(cost(),review(),ContractPaymentCalendarRequest.model_validate(d))['status']=='UNKNOWN'


def test_mixed_file_or_incomplete_literal_rejected():
    for change in ('file','quote'):
        packet=review()
        fragment=packet['groups']['acceptance_payment']['source_sections']['4.3']['fragments'][0]
        fragment['file_id' if change=='file' else 'quote']='foreign'
        assert project_payment_calendar(cost(),packet,contract_calendar_fixture())['status']=='UNKNOWN'


def test_local_cli_generated_schedule(monkeypatch,tmp_path,capsys):
    from scripts.acceptance import review_ri223_archived_owner as cli

    p=tmp_path/'price.json';p.write_text(cost().model_dump_json())
    q=tmp_path/'schedule.json';q.write_text(contract_calendar_fixture().model_dump_json())
    def run(run_id,scenario,*,include_decision,cash_calendar,contract_payment_calendar):
        assert run_id=='pinned' and include_decision and cash_calendar is None
        return project_payment_calendar(scenario,review(),contract_payment_calendar)
    monkeypatch.setattr(cli,'review_archived_owner_run',run)
    argv=['review','--run-id','pinned','--scenario-json',str(p),'--contract-payment-calendar-json',str(q),'--decision']
    monkeypatch.setattr('sys.argv',argv)
    cli.main()
    assert '"modeled_bank_receipt_date": "2027-02-14"' in capsys.readouterr().out
    monkeypatch.setattr('sys.argv',[*argv,'--cash-calendar-json',str(q)])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code==2
