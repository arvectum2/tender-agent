"""MI-013 extended 82-case evidence integrity, without touching 71-row production DB."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/"scripts/market_intelligence"
DATA=ROOT/"data/market_intelligence/power_quality"

def read(version):
    out=subprocess.run([sys.executable,str(SCRIPTS/f"materialize_pq_research_v{version}.py")],
        check=True,capture_output=True,text=True,timeout=40)
    return json.loads(out.stdout)

def test_v14_only_appends_three_procurement_signals():
    old,new=read(13),read(14)
    assert len(old["records"])==79
    assert len(new["records"])==82
    assert new["records"][:79]==old["records"]
    assert len({r["canonical_id"] for r in new["records"]})==82
    assert {x["procedure_id"] for x in new["records"][79:]}=={
        "32615966040","COM20082600016","1351/ОАЭ-ЦДКС/26"
    }

def test_v14_preserves_contract_uncertainty_for_10kv_mixed_epc():
    records=read(14)["records"][79:]
    nik=next(r for r in records if r["procedure_id"]=="32615966040")
    assert nik["nmck_rub"]=="5273764.00"
    assert nik["reported_contract_total_rub"]=="5273764.00"
    assert nik["reported_contract_date"]=="2026-06-03"
    assert nik["reported_contract_total_source_tier"].startswith("secondary")
    assert nik["equipment_voltage_kv"] is None
    assert nik["pq_equipment_only_contract_rub"] is None
    assert not nik["supplier_verified"]

def test_v14_market_sounding_and_auxiliary_work_are_not_device_sales():
    rows=read(14)["records"][79:]
    ukrm=next(r for r in rows if r["procedure_id"]=="COM20082600016")
    rail=next(r for r in rows if r["procedure_id"]=="1351/ОАЭ-ЦДКС/26")
    assert ukrm["scope"]=="market_sounding"
    assert ukrm["nmck_rub"] is None
    assert rail["scope"]=="electrical_auxiliary_works"
    assert rail["nmck_rub"]=="36289595.00"
    assert all(r["pq_equipment_only_contract_rub"] is None for r in rows)

def test_rolling_window_and_staging_counts_protect_live_v12():
    dataset=read(14)
    assert len(dataset["records"])==82
    assert dataset["verification_summary"]["production_structured_records_imported"]==71
    assert dataset["verification_summary"]["new_records_pending_import"]==11
    assert dataset["verification_summary"]["primary_signed_contracts_added"]==0
    for r in dataset["records"][71:]:
        assert "2023-10-27" <= r["publication_date"] <= "2026-10-27"
        assert r["evidence"][0]["url"].startswith("https://")
