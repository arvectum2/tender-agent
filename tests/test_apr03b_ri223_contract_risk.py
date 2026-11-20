import pytest

from src.modules.tender_operator_agent_demo import ri223_contract_risk as risk


def fixture(monkeypatch, *, mismatch=False, missing=()):
    lineage={'member_sha256':risk._SHA,'member_path':risk._MEMBER}
    record={'file_id':'FILE-04','source':'ri223_container_member','ri223_container':lineage}
    monkeypatch.setattr(risk,'verified_container_lineage',lambda *a:None if mismatch else lineage)
    forbidden={x[2] for x in risk._CLAUSES if x[0] in missing}
    def verify(**kwargs):
        quote=kwargs['exact_quote']
        return {'status':'unverified','evidence':None} if quote in forbidden else {
            'status':'literal_quote_found_in_extracted_original_only',
            'evidence':{'original_sha256':risk._SHA,'quote':quote,'ri223_container':lineage}}
    monkeypatch.setattr(risk,'verify_operator_run_quote',verify)
    return {'procurement_id':risk._NUMBER,'files':[record]}


@pytest.mark.parametrize('missing',[(),('delay_penalty',),('assignment',)])
def test_contract_exposure_is_conditional(monkeypatch,tmp_path,missing):
    m=fixture(monkeypatch,missing=missing)
    scenario={'status':'ARCHIVED_LOT_EXPLICIT_SCENARIO_ONLY','calculation':{'offer_scenario':{'offer_price_rub':'900000'}}}
    out=risk.observe_contract_risk('test',tmp_path,m,scenario)
    assert out['verified_clause_count']==14-len(missing)
    e=out['scenario_exposure']
    assert e['daily_delay_penalty_rub']==(None if 'delay_penalty' in missing else '900.00')
    assert e['unauthorized_assignment_penalty_rub']==(None if 'assignment' in missing else '180000.00')
    assert e['actual_liability_rub'] is None and e['all_sanctions_additive'] is None
    assert out['liability_cap_rub'] is None and out['subcontract_variant_selected'] is None
    assert not out['go_eligible'] and not out['final_contract_verified']


def test_unknown_without_scenario(monkeypatch,tmp_path):
    m=fixture(monkeypatch)
    out=risk.observe_contract_risk('test',tmp_path,m,{})
    assert out['scenario_exposure'] is None


@pytest.mark.parametrize('change',['number','duplicate','tamper'])
def test_unbound_contract_never_attests(monkeypatch,tmp_path,change):
    m=fixture(monkeypatch,mismatch=change=='tamper')
    if change=='number':m['procurement_id']='32600000000'
    elif change=='duplicate':m['files']*=2
    monkeypatch.setattr(risk,'verify_operator_run_quote',lambda **kw:pytest.fail('unbound quote called'))
    assert risk.observe_contract_risk('test',tmp_path,m,{})['status']=='UNKNOWN'
