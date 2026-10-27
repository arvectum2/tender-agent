"""MI-013 v18: assert new 6.3/10kV lines, no promotion to signed awards."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS=Path(__file__).resolve().parents[1]/"scripts/market_intelligence"

def corpus(v):
    p=subprocess.run([sys.executable,str(SCRIPTS/f"materialize_pq_research_v{v}.py")],
                     capture_output=True,text=True,check=True,timeout=40)
    return json.loads(p.stdout)

def test_v18_appends_two_preserving_prior_99():
    old=corpus(17)["records"]
    new=corpus(18)["records"]
    assert len(old)==99 and len(new)==101
    assert new[:99]==old
    assert len({r["canonical_id"] for r in new})==101
    assert corpus(18)["verification_summary"]["production_structured_records_imported"]==71
    assert corpus(18)["verification_summary"]["new_records_pending_import"]==30

def test_argos_6p3kv_mixed_mtr_market_sounding_not_equipment_sale():
    r=next(x for x in corpus(18)["records"] if x.get("procedure_id")=="4559984")
    assert r["equipment_voltage_kv"]==6.3
    assert r["quantity"]==1
    assert r["equipment_model"]=="АУКРМ-6,3-1350-450-12 УХЛ4"
    assert r["equipment_reactive_power_mvar"] is None
    assert r["scope"]=="mixed_MTR_market_sounding_with_PQ_component"
    assert r["nmck_rub"] is None and r["pq_equipment_only_contract_rub"] is None
    assert not r["supplier_verified"]

def test_tobolsk_2025_filter_reactor_no_official_EIS_claim():
    r=next(x for x in corpus(18)["records"] if x["canonical_id"]=="index:rostender:88416730")
    assert r["publication_date"]=="2025-12-02"
    assert r["equipment_voltage_kv"]==10
    assert r["procedure_id"] is None
    assert r["source_identifier_masked"] is True
    assert r["family"]=="harmonic_filter_reactor"
    assert r["nmck_rub"] is None and r["reported_contract_total_rub"] is None

def test_total_years_and_initial_prices_unchanged():
    rows=corpus(18)["records"]
    years={}
    for r in rows:
        y=(r.get("publication_date") or "undated")[:4]
        years[y]=years.get(y,0)+1
    assert years=={"2023":3,"2024":17,"2025":23,"2026":55,"unda":3}
    assert all(x["source_identifier_masked"] is True for x in rows[-1:])
