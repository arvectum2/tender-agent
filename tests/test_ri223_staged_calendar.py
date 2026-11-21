import pytest
from test_operator_cashflow_calendar import cost

from scripts.acceptance.apr03b_cash_calendar_fixture import calendar_fixture
from scripts.acceptance.apr03b_staged_fixture import advance, inputs
from src.modules.tender_operator_agent_demo.ri223_staged_calendar import (
    StagedRequest,
    _compute,
    _withholding_stress,
)
from src.modules.tender_operator_agent_demo.ri223_staged_evidence import (
    partition_paragraph,
)

TERMS={'procurement_id':'32616445632','complete_reviewed_groups':True}


def test_partition_full_not_spliced():
    a='Заказчик оплачивает оказанные услуги.'
    b='Исполнитель предоставляет счет.'
    q=a+' '+b
    assert partition_paragraph(q,[a,b])==(a,b)
    assert partition_paragraph(q,[a]) is None
    assert partition_paragraph(q,[a,a,b]) is None


def test_staged_and_discretionary_advance():
    c,req=inputs()
    m=_compute(c,TERMS,req)
    a=_compute(c,TERMS,advance(req))
    assert len(m['generated_events'])==12 and len(a['generated_events'])==1
    assert m['projections'][0]['modeled_credit_date']=='2026-11-12'
    assert m['cash_calendar']['scenario_net_cash_rub']==a['cash_calendar']['scenario_net_cash_rub']=='51021.60'
    assert not m['go_eligible'] and not a['advance_guaranteed']
    assert a['cash_calendar']['cases'][0]['peak_funding_required_rub']=='7000.00'
    assert m['cash_calendar']['cases'][0]['peak_funding_required_rub']=='14000.00'


@pytest.mark.parametrize('change',['late_invoice','acceptance_after_docs','missing_month','wrong_sum','manual_receipt','duplicate_month'])
def test_invalid_staged_inputs(change):
    c,req=inputs();d=req.model_dump()
    if change=='late_invoice':d['monthly'][0]['invoice_issued']='2026-11-06'
    elif change=='acceptance_after_docs':d['monthly'][0]['accepted_date']='2026-11-04'
    elif change=='missing_month':d['monthly'].pop(1)
    elif change=='wrong_sum':d['monthly'][0]['amount_rub']='11969.99'
    elif change=='manual_receipt':d['ledger_without_customer_receipts']['events'][0]['category']='advance'
    elif change=='duplicate_month':d['monthly'][1]=d['monthly'][0]
    with pytest.raises(ValueError):
        _compute(c,TERMS,StagedRequest.model_validate(d))


def test_unknown_terms_or_customer_election():
    c,req=inputs()
    assert _compute(c,{},req)['status']=='UNKNOWN'
    a=advance(req).model_copy(update={'assume_customer_elected_full_advance':False})
    assert _compute(c,TERMS,a)['status']=='UNKNOWN'
    assert _compute(c,TERMS,req.model_copy(update={'assume_draft_annex_controls_for_scenario':False}))['status']=='UNKNOWN'


def test_withholding_is_nonreceipt_not_security():
    out=_withholding_stress(cost(),calendar_fixture(),'e06','100000',{})
    assert out['net_cash_after_assumed_nonreceipt_rub']=='272000.00'
    assert out['cases'][0]['ending_net_cash_rub']=='272000.00'
    assert out['cases'][0]['peak_funding_required_rub']=='345000.00'
    assert out['refund_date'] is None and out['actual_liability_rub'] is None


@pytest.mark.parametrize('amount',['-1','0','NaN','270000.01','0.001'])
def test_invalid_withholding(amount):
    with pytest.raises(ValueError):
        _withholding_stress(cost(),calendar_fixture(),'e06',amount,{})


def test_local_staged_cli(monkeypatch,tmp_path,capsys):
    from scripts.acceptance import review_ri223_staged_calendar as cli
    c,req=inputs()
    p=tmp_path/'price.json';p.write_text(c.model_dump_json())
    q=tmp_path/'staged.json';q.write_text(req.model_dump_json())
    def run(run_id,price,schedule):
        assert run_id=='pinned'
        return _compute(price,TERMS,schedule)
    monkeypatch.setattr(cli,'review_staged_calendar',run)
    args=['review','--run-id','pinned','--scenario-json',str(p),'--staged-json',str(q)]
    monkeypatch.setattr('sys.argv',args)
    cli.main()
    assert '"status": "CONDITIONAL_STAGED_SETTLEMENT_ONLY"' in capsys.readouterr().out
    monkeypatch.setattr('sys.argv',[*args,'--withholding-json',str(q)])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code==2


def test_contiguous_context_resolves_overlap():
    a='Сумма определяется в следующем порядке.'
    b='Подлежит возмещению установленная сумма.'
    c='При этом учитывается дополнительное обстоятельство.'
    assert partition_paragraph(b,[a+' '+b,b+' '+c]) is None
    assert partition_paragraph(a+' '+b+' '+c,[a+' '+b,b+' '+c])==(a+' '+b,c)
