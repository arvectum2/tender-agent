"""Checklist rules with synthetic source receipts and no private data."""
import pytest

from src.modules.company_profile_store import application_checklist as app
from src.modules.tender_operator_agent_demo.ri223_application_source import (
    SOURCE_PARAGRAPHS,
)


def packet():
    return {'status':'ARCHIVED_QUOTATION_CHECKLIST_REVIEW_ONLY','procurement_number':'32616444788',
            'source_groups':{sha:{k:[{'quote':q,'fixture':True}] for k,q in items.items()} for sha,items in SOURCE_PARAGRAPHS.items()}}


@pytest.mark.parametrize('signatory,goods,poa,delegated,description',[
    ('UNKNOWN',None,'CONDITIONAL_UNKNOWN','CONDITIONAL_UNKNOWN','CONDITIONAL_UNKNOWN'),
    ('DIRECTOR',False,'NOT_TRIGGERED_IN_SCENARIO','NOT_TRIGGERED_IN_SCENARIO','NOT_TRIGGERED_IN_SCENARIO'),
    ('REPRESENTATIVE',True,'REQUIRED_IN_SCENARIO','NOT_TRIGGERED_IN_SCENARIO','REQUIRED_IN_SCENARIO'),
    ('DELEGATED_SIGNER',False,'REQUIRED_IN_SCENARIO','REQUIRED_IN_SCENARIO','NOT_TRIGGERED_IN_SCENARIO')])
def test_conditions(signatory,goods,poa,delegated,description):
    rows={r['code']:r for r in app._rows(packet(),signatory,goods)}
    assert len(rows)==9
    assert rows['director_appointment']['applicability']=='REQUIRED'
    assert rows['power_of_attorney']['applicability']==poa
    assert rows['delegated_signer_authority']['applicability']==delegated
    assert rows['goods_description']['applicability']==description
    assert rows['software_distribution_rights']['applicability']=='OPTIONAL_EVIDENCE_NOT_OPTIONAL_RIGHTS'
    assert len(rows['software_distribution_rights']['claims'])==2
    assert all(r['source'] and r['satisfied'] is None for r in rows.values())


@pytest.mark.parametrize('status',['UNKNOWN','ARCHIVED_NOTIFICATION_NOT_APPLICATION','INCOMPLETE_REVIEWED_SOURCE'])
def test_no_application_from_unverified_or_noncompetitive(status):
    assert app._rows({'status':status},'DIRECTOR',False)==[]


def test_candidate_not_compliance(monkeypatch):
    monkeypatch.setattr(app,'observe_application',lambda run:packet())
    def profile(*args,requirements,**kwargs):
        assert 'power_of_attorney' not in requirements
        return {'requirements':[{'requirement_code':k,'state':'DOCUMENTED_OWNER_CLAIM_REVIEW_REQUIRED' if k=='partner_certificate' else 'MISSING',
                                 'claim_assertion':'PRESENT' if k=='partner_certificate' else None} for k in requirements]}
    monkeypatch.setattr(app,'review_profile',profile)
    r=app.review_application(None,customer_id='owner',root=None,run_id='fixture',signatory='DIRECTOR',goods_used=False)
    rows={x['code']:x for x in r['rows']}
    assert rows['software_distribution_rights']['state']=='CANDIDATE_REVIEW_REQUIRED'
    assert rows['director_appointment']['state']=='DOCUMENTARY_EVIDENCE_MISSING_OR_UNCONFIRMED'
    assert not r['application_ready'] and not r['signed'] and not r['submitted']
    assert r['recommendation']=='DEFER' and not r['go_eligible']


def test_invalid_scenario():
    with pytest.raises(ValueError):
        app._rows(packet(),'INVALID',None)
    with pytest.raises(ValueError):
        app._rows(packet(),'DIRECTOR',1)


def test_observer_blocks_missing_group(monkeypatch,tmp_path):
    meta={'procurement_id':'32616444788'}
    monkeypatch.setattr(app,'checked_search_run',lambda run:(tmp_path,meta))
    monkeypatch.setattr(app,'verified_inventory',lambda *a:{'archived_bytes_complete':True,'projection_complete':True})
    monkeypatch.setattr(app,'ri223_archive_observation',lambda *a:{'status':'PINNED_RI223_ARCHIVED_NOTICE'})
    def attest(*args,paragraphs,**kwargs):
        return {k:[{'quote':q}] for k,q in paragraphs.items() if k!='appointment'}
    monkeypatch.setattr(app,'_attest',attest)
    pkt=app.observe_application('fixture')
    assert pkt['status']=='INCOMPLETE_REVIEWED_SOURCE'
    assert app._rows(pkt,'DIRECTOR',False)==[]


def test_observer_blocks_changed_original_inventory(monkeypatch,tmp_path):
    meta={'procurement_id':'32616444788'}
    monkeypatch.setattr(app,'checked_search_run',lambda run:(tmp_path,meta))
    inventories=iter([{'archived_bytes_complete':True,'projection_complete':True},
                      {'archived_bytes_complete':False,'projection_complete':True}])
    monkeypatch.setattr(app,'verified_inventory',lambda *a:next(inventories))
    monkeypatch.setattr(app,'ri223_archive_observation',lambda *a:{'status':'PINNED_RI223_ARCHIVED_NOTICE'})
    monkeypatch.setattr(app,'_attest',lambda *args,paragraphs,**kwargs:{k:[{'quote':q}] for k,q in paragraphs.items()})
    assert app.observe_application('fixture')['status']=='UNKNOWN'
