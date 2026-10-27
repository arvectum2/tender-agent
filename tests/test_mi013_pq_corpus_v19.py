"""MI-013 v19: one evidence-driven retraction, enrichment of existing real notices."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/market_intelligence"

def read(v):
    p=subprocess.run([sys.executable,str(SCRIPT/f"materialize_pq_research_v{v}.py")],
        capture_output=True,text=True,check=True,timeout=45)
    return json.loads(p.stdout)

def test_v19_retracts_only_false_mogocha_2024_and_preserves_original_2023_eis():
    old=read(18)["records"]
    result=read(19)
    new=result["records"]
    assert len(old)==101 and len(new)==100
    assert {x["canonical_id"] for x in old}-{x["canonical_id"] for x in new}=={
        "index:energybase:mogocha-statcom-cooling-20240415",
    }
    e=next(x for x in new if x.get("procedure_id")=="32313008364")
    assert e["publication_date"]=="2023-11-27"
    assert e["nmck_rub"]=="6795960"
    assert e.get("supplier_verified") is not True
    assert len(result["retracted_observations"])==1
    assert result["retracted_observations"][0]["confirmed_real_notice_id"]=="32313008364"

def test_statcom_three_confirmed_quantity_not_won_units():
    r=next(x for x in read(19)["records"] if x.get("procedure_id")=="106044-ТТ")
    assert r["reported_equipment_quantity"]==3
    assert [x["quantity"] for x in r["equipment_split"]]==[2,1]
    assert r["underlying_supplier_contract_verified"] is False
    assert any("IS55137357" in e["url"] for e in r["evidence"])

def test_joint_oil_tender_four_beneficiaries_one_notice_not_four_sales():
    rows=read(19)["records"]
    r=next(x for x in rows if x.get("procedure_id")=="РН41205245")
    assert r["joint_buyers_count"]==4
    assert len(r["joint_beneficiaries"])==4
    assert len({x["inn"] for x in r["joint_beneficiaries"]})==4
    assert sum(x.get("procedure_id")=="РН41205245" for x in rows)==1
    assert r.get("reported_contract_total_rub") is None
    assert r["supplier_verified"] is False

def test_ufimka_only_one_bid_failed_but_later_signed_contract_secondary():
    r=next(x for x in read(19)["records"] if x.get("procedure_id")=="32514476448")
    assert r["tender_results_procedure_status"]=="competitive_procedure_failed_only_one_admitted_bid"
    assert r["contract_conclusion_reported_secondary"] is True
    assert r["reported_registered_contract_number"]=="50277071467250001900000"
    assert r["reported_registered_contract_date"]=="2025-03-26"
    assert r["reported_contract_total_rub"]=="2922405.35"
    assert r["winning_supplier_identity_primary_verified"] is False

def test_v19_year_totals_and_old_live_data_identity():
    rows=read(19)["records"]
    years={}
    for r in rows:
        y=(r.get("publication_date") or "undated")[:4]
        years[y]=years.get(y,0)+1
    assert years=={"2023":3,"2024":16,"2025":23,"2026":55,"unda":3}
    assert sum(r.get("nmck_rub") is not None for r in rows)==36
    assert len({x["canonical_id"] for x in rows})==100
    assert len(rows[:71])==71
    assert read(19)["verification_summary"]["production_structured_records_imported"]==71
    assert read(19)["verification_summary"]["new_records_pending_import"]==29
