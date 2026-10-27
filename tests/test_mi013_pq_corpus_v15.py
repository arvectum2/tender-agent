"""v15 source reliability, project reissue and excluded-market safeguards."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/"scripts/market_intelligence"
DATA=ROOT/"data/market_intelligence/power_quality"

def load(v):
    p=subprocess.run([sys.executable,str(SCRIPTS/f"materialize_pq_research_v{v}.py")],check=True,capture_output=True,text=True,timeout=35)
    return json.loads(p.stdout)

def test_v15_preserves_82_and_appends_two_unique_source_ids():
    old=load(14)["records"]
    now=load(15)["records"]
    assert len(old)==82
    assert len(now)==84
    assert now[:82]==old
    assert len({r["canonical_id"] for r in now})==84
    assert {r["canonical_id"] for r in now[-2:]}=={
      "223fz:32616400421:lot1",
      "index:vsempodryad:ea5a381b-31b1-4c37-962f-9fddf1761b74"
    }

def test_v15_cancelled_452m_original_not_double_counted_sale():
    rows=load(15)["records"]
    t=next(x for x in rows if x["procedure_id"]=="32616400421")
    r=next(x for x in rows if x["procedure_id"]=="32616435269")
    assert t["status"]=="CANCELLED"
    assert t["nmck_rub"]==r["nmck_rub"]=="452016000.01"
    assert t["demand_group"]=="TYAZHINSKAYA-SKRM52-2025-2026"
    assert r["procedure_id"] in t["potential_same_demand_as"]
    assert t["reported_contract_total_rub"] is None
    assert not t["supplier_verified"]

def test_v15_2024_volgogradenergo_keeps_eis_id_masked():
    new=load(15)["records"][-1]
    assert new["procedure_id"] is None
    assert new["source_identifier_masked"] is True
    assert new["quantity"]==7
    assert new["nmck_rub"]=="10880835.00"
    assert new["reported_contract_total_rub"]=="10880835.00"
    assert new["reported_contract_total_source_tier"].startswith("secondary")
    assert new["reported_contract_date"]=="2024-08-15"
    assert new["supplier_verified"] is False
    assert new["equipment_voltage_kv"] is None

def test_v15_production_import_did_not_change_with_research():
    s=load(15)["verification_summary"]
    assert s["production_structured_records_imported"]==71
    assert s["new_records_pending_import"]==13
    assert s["total_lot_level_records"]==84
    assert s["original_signed_contract_xml_known_count"]==4
    assert s["market_population_complete"] is False
