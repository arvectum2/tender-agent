"""MI-013 full rolling 3-year second-pass evidence checks."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/"data/market_intelligence/power_quality"
SCRIPT=ROOT/"scripts/market_intelligence/materialize_pq_research_v13.py"


def v13():
    p=subprocess.run([sys.executable,str(SCRIPT)],capture_output=True,text=True,check=True,timeout=35)
    return json.loads(p.stdout)


def test_v13_adds_8_unique_notices_to_71_without_changing_prior_data():
    from importlib.util import spec_from_file_location, module_from_spec
    sys.path.insert(0,str(SCRIPT.parent))
    try:
        from materialize_pq_research_v12 import materialize as v12
        old=v12()["records"]
    finally:
        sys.path.remove(str(SCRIPT.parent))
    new=v13()["records"]
    assert len(old)==71
    assert len(new)==79
    assert old==new[:71]
    assert len({r["canonical_id"] for r in new})==79
    assert {r["procedure_id"] for r in new[71:]}=={
        "231994","231994-2","32615794236","32413708738",
        "32514944142","32616339168","32515584863","32615760238",
    }


def test_2023_2026_window_maintained_and_no_fake_awards():
    delta=json.loads((DIR/"discovery_2023_2026_v13_delta.json").read_text())
    assert len(delta["records"])==8
    for entry in delta["records"]:
        assert "2023-10-27"<=entry["published"]<="2026-10-27"
        assert entry["source"].startswith("https://")
    x=v13()
    assert x["verification_summary"]["production_structured_records_imported"]==71
    assert x["verification_summary"]["new_records_pending_import"]==8
    assert x["verification_summary"]["new_primary_verified_award_count"]==0
    assert all(r["supplier_verified"] is False for r in x["records"][71:])


def test_2025_26_project_reissues_grouped_and_outside_scope_hv():
    rows=v13()["records"][71:]
    groups={k:[r for r in rows if r["demand_group"]==k] for k in {
        "APATIT-KIROVSK-GS2-PS352-DYNAMIC-REACTIVE-2026",
        "ROSSETI-HANI-LOPCHA-SKRM-128-154-2025-26",
    }}
    assert len(groups["APATIT-KIROVSK-GS2-PS352-DYNAMIC-REACTIVE-2026"])==2
    assert len(groups["ROSSETI-HANI-LOPCHA-SKRM-128-154-2025-26"])==2
    chadan=next(r for r in rows if r["procedure_id"]=="32615794236")
    assert chadan["equipment_voltage_kv"]==110
    assert chadan["market_scope"]=="outside_strict_6_35kv"
    assert chadan["reported_contract_total_rub"]=="3579778.90"
    assert chadan["reported_contract_total_source_tier"].startswith("secondary")
    bsk24=next(r for r in rows if r["procedure_id"]=="32616339168")
    assert bsk24["equipment_voltage_kv"] is None
    assert bsk24["quantity"] is None  # 24 components in title, not 24 full BSK systems
    assert bsk24["nmck_rub"]=="6807600.00"


def test_2024_large_220kv_epc_not_attributed_to_6_35():
    row=next(r for r in v13()["records"] if r["procedure_id"]=="32413708738")
    assert row["publication_date"]=="2024-07-29"
    assert row["equipment_voltage_kv"]==220
    assert row["nmck_rub"]=="826223180.00"
    assert row["pq_equipment_only_contract_rub"] is None
    assert row["market_scope"]=="outside_strict_6_35kv"
