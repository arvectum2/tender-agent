"""Validate all 68 staged PQ market-intelligence resources without database writes."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"market_intelligence"/"export_pq_data_platform_v10.py"
DATA=ROOT/"data"/"market_intelligence"/"power_quality"

def export():
    p=subprocess.run([sys.executable,str(SCRIPT)],capture_output=True,text=True,check=True,timeout=30)
    return [json.loads(line) for line in p.stdout.splitlines() if line.strip()]

def test_v10_68_resources_have_stable_ids_and_correct_version():
    rows=export()
    assert len(rows)==68
    assert len({r["canonical_uri"] for r in rows})==68
    assert len({r["external_id"] for r in rows})==68
    for r in rows:
        digest=hashlib.sha256(r["external_id"].encode("utf-8")).hexdigest()
        assert r["resource_id"]==digest[:48]
        assert r["canonical_uri"]=="urn:arvectum:pq:procurement:"+digest
        assert r["metadata"]["data_version"]=="v10"
        assert r["metadata"]["research_not_market_population"] is True

def test_v10_never_infers_vendor_or_hardware_component_price():
    rows=export()
    extra={x["source_record"]["procedure_id"]:x for x in rows[-4:]}
    assert set(extra)=={"32514476448","32515044454","32616354211","RAD260049805"}
    for r in extra.values():
        assert r["metadata"]["winning_supplier_only_if_verified"] is None
        assert r["metadata"]["original_primary_registry_verified"] is False
        assert r["source_record"]["pq_equipment_only_contract_rub"] is None
    assert extra["RAD260049805"]["source_record"]["nmck_rub"] is None
    assert extra["RAD260049805"]["metadata"]["reported_price_kind"] is None
    assert extra["32514476448"]["source_record"]["equipment_voltage_kv"]==10
    assert extra["RAD260049805"]["source_record"]["equipment_voltage_kv"]==35

def test_v10_snapshot_denominators_and_versioned_repeat_group():
    snap=json.loads((DATA/"evidence_quality_snapshot_20261027.v10.json").read_text())
    rows=export()
    assert snap["procurement_records"]==len(rows)==68
    assert snap["canonical_ids_unique"]==68
    assert sum(r["source_record"]["nmck_rub"] is not None for r in rows)==snap["nmck_any_non_null_count"]==20
    assert snap["regime_counts"]=={"223-fz":22,"commercial":46}
    assert sum(snap["family_counts"].values())==68
    assert sum(snap["scope_counts"].values())==68
    assert snap["registered_contract_primary_verified_count"]==4
