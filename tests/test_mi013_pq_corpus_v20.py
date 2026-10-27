"""MI-013 v20 original protocol legal-entity evidence acceptance."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS=Path(__file__).resolve().parents[1]/"scripts/market_intelligence"

def corpus(v):
    p=subprocess.run([sys.executable,str(SCRIPTS/f"materialize_pq_research_v{v}.py")],
        text=True,capture_output=True,check=True,timeout=45)
    return json.loads(p.stdout)

def get(rows,notice):
    return next(x for x in rows if x.get("procedure_id")==notice)

def test_v20_does_not_add_extra_notices_or_overwrite_existing_100_rows():
    b=corpus(19)["records"]
    a=corpus(20)["records"]
    assert len(a)==len(b)==100
    assert [r["canonical_id"] for r in a]==[r["canonical_id"] for r in b]
    for old,new in zip(b,a):
        if "protocol_role_evidence" in new:
            extra={"protocol_role_evidence","protocol_role_interpretation","protocol_role_original_sources"}
            assert {k:v for k,v in new.items() if k not in extra}==old
        else:
            assert new==old

def test_two_protocol_named_bidder_roles_not_manufacturer_revenue():
    rows=corpus(20)["records"]
    k=get(rows,"32616433248")["protocol_role_evidence"]
    assert k["original_protocol_named_bidder"]=="ООО «СТРОЙЭНЕРГОИМПОРТ»"
    assert k["original_protocol_named_bidder_inn"]=="7801564611"
    assert k["original_protocol_accepted_bid_rub"]=="56330673.93"
    assert k["original_registry_contract_verified"] is False
    assert k["original_protocol_ukrm_min_mvar"]==3.5
    assert k["equipment_cost_is_signed_sale"] is False
    assert k["original_equipment_cost_base_year_2025_rub"]=="10780666.67"
    n=get(rows,"32615614821")["protocol_role_evidence"]
    assert n["original_protocol_named_bidder"]=="ООО «ТЕХНОПРОМ»"
    assert n["original_protocol_accepted_bid_rub"]=="1833358.30"
    assert n["original_registry_contract_verified"] is True
    assert n["original_registry_supplier_identity_verified"] is False
    assert n["original_equipment_voltage_kv"]==6.3

def test_ango_vodokanal_offer_differs_from_actual_registry_contract_price():
    x=get(corpus(20)["records"],"32616412267")["protocol_role_evidence"]
    assert x["bid_submission_count"]==3
    assert x["original_protocol_lowest_bid_rub"]=="2590000.00"
    assert x["original_registry_contract_price_rub"]=="2639026.64"
    assert x["bid_vs_signed_price_not_equal"] is True
    assert x["new_equipment_purchase_verified"] is False
    assert x["already_installed_ukrm_count"]==2

def test_other_contract_17m_and_zero_bid_design_not_added_as_new_equipment():
    rows=corpus(20)["records"]
    a=get(rows,"32616120582")["protocol_role_evidence"]
    assert a["original_protocol_winning_application_id"]=="4149972340"
    assert a["original_registry_contract_price_rub"]=="17000000.00"
    assert a["original_protocol_named_bidder"] is None
    b=get(rows,"32615969197")["protocol_role_evidence"]
    assert b["bid_submission_count"]==0
    assert b["original_protocol_result"]=="failed_zero_applications"
    assert b["scope_not_equipment_sale"] is True

def test_count_primary_protocol_sources_proven_and_no_new_supplier_identity():
    z=corpus(20)
    assert z["verification_summary"]=={
        "total_lot_level_records":100,
        "existing_records_with_new_primary_protocol_data":5,
        "new_notices_added":0,
        "named_tender_bidders_in_addendum":2,
        "signed_contract_supplier_identity_newly_verified":0,
        "total_original_Rd223_signed_contracts":4,
        "production_structured_records_imported":71,
        "new_records_pending_import":29,
        "market_population_complete":False,
    }
    assert all(x.get("tier", x.get("source_tier","")).startswith(("original","independent","RD223_original")) for r in z["records"] for x in r.get("protocol_role_original_sources",[]) )
