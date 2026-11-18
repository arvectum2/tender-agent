from copy import deepcopy

import pytest

from src.modules.tender_operator_agent_demo.ri223_decision_review import (
    archived_decision_projection,
)


def fixture():
    fields={"subject":"Archived fixture","single_lot_initial_sum":"1020000","single_lot_currency":"RUB",
            "archived_submission_deadline":"2026-10-15T10:00:00"}
    n={"status":"PINNED_RI223_ARCHIVED_NOTICE","lot_count":1,"fields":fields,
       "citations":[{"source_ref":"ri223-xml:"+("a"*64)+":"+k,"excerpt":v} for k,v in fields.items()]}
    i={"archived_bytes_complete":True,"projection_complete":True}
    d={"status":"RI223_ARCHIVED_REVIEW_ONLY","notice":deepcopy(n),"inventory":deepcopy(i)}
    r={"clauses":[{"status":"VERIFIED_LITERAL_FRAGMENT","operator_review_note":"Test clause review","section":"5.3",
       "source":{"quote":"Exact original fixture clause","original_sha256":"b"*64,"chunk_id":"fixture",
                 "ri223_container":{"member_path":"contract.docx"}}}]}
    e={"offer_within_archived_initial_sum":True}
    return n,i,d,r,e


@pytest.mark.parametrize("change",["missing_inventory","opaque","wrong_notice","wrong_dossier","wrong_inventory"])
def test_consistency_required(change):
    n,i,d,r,e=fixture()
    if change=="missing_inventory":i["archived_bytes_complete"]=False
    elif change=="opaque":i["projection_complete"]=False
    elif change=="wrong_notice":n["fields"]["subject"]="Changed"
    elif change=="wrong_dossier":d["status"]="UNKNOWN"
    else:d["inventory"]["extra"]=True
    out=archived_decision_projection(n,i,d,r,e)
    assert out["status"]=="UNKNOWN" and "decision_core" not in out and out["recommendation"]=="DEFER"


@pytest.mark.parametrize("within",[True,False,None])
def test_scenario_cannot_promote_go_or_no_go(within):
    n,i,d,r,e=fixture()
    e["offer_within_archived_initial_sum"]=within
    out=archived_decision_projection(n,i,d,r,e)
    assert out["status"]=="ARCHIVED_DECISION_REVIEW_ONLY"
    assert out["recommendation"]=="DEFER" and not out["go_eligible"]
    assert out["decision_core"]["decision"]["status"]=="NEEDS_REVIEW"
    assert not out["decision_core"]["supplier_profile_bound"]
    assert out["scenario_price_comparison"] is within
    assert out["decision_core"]["facts"]["application_deadline"]["status"]=="UNKNOWN"
    assert out["decision_core"]["facts"]["nmck"]["value"]=="1020000"
    assert not out["decision_core"]["blockers"]
    assert len(out["review_gates"])==9
    assert all(not v for v in out["decision_core"]["safety"].values())


def test_multilot_no_aggregate_and_unverified_clause_excluded():
    n,i,d,r,e=fixture()
    n["lot_count"]=2;d["notice"]=deepcopy(n)
    r["clauses"][0]["status"]="UNKNOWN"
    out=archived_decision_projection(n,i,d,r,e)
    assert out["decision_core"]["facts"]["nmck"]["status"]=="UNKNOWN"
    assert not out["decision_core"]["facts"]["contract_draft"]["evidence"]
    assert out["recommendation"]=="DEFER"


def test_verified_risk_incomplete_fails_closed():
    n,i,d,r,e=fixture()
    r['verified_clause_count']=1
    del r['clauses'][0]['source']['chunk_id']
    assert archived_decision_projection(n,i,d,r,e)['reason']=='VERIFIED_RISK_LINEAGE_INCOMPLETE'


def test_verified_risk_count_mismatch_fails_closed():
    n,i,d,r,e=fixture()
    r['verified_clause_count']=2
    assert archived_decision_projection(n,i,d,r,e)['reason']=='VERIFIED_RISK_COUNT_MISMATCH'


def test_evidence_retained_and_consistency_not_assumed():
    n,i,d,r,e=fixture()
    out=archived_decision_projection(n,i,d,r,e)
    assert len(out['projected_risk_evidence'])==1
    assert len(out['decision_core']['facts']['contract_draft']['evidence'])==1
    assert next(x for x in out['decision_core']['readiness'] if x['code']=='SOURCE_CONSISTENCY')['status']=='REVIEW'
