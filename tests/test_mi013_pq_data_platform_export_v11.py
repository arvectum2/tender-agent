"""v11 Data Platform staging preserves lot granularity without extra revenue."""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/market_intelligence/export_pq_data_platform_v11.py"


def export():
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                            text=True, check=True, timeout=35)
    return [json.loads(x) for x in result.stdout.splitlines() if x.strip()]


def test_v11_staged_71_stable_resources_with_unique_ids():
    records = export()
    assert len(records) == 71
    assert len({r["resource_id"] for r in records}) == 71
    assert len({r["external_id"] for r in records}) == 71
    assert all(r["metadata"]["data_version"] == "v11" for r in records)
    for row in records:
        hash_ = hashlib.sha256(row["external_id"].encode("utf-8")).hexdigest()
        assert row["resource_id"] == hash_[:48]
        assert row["canonical_uri"] == "urn:arvectum:pq:procurement:" + hash_
        assert row["metadata"]["research_not_market_population"] is True


def test_v11_staged_joint_lots_not_winner_or_equipment_voltage():
    last = export()[-3:]
    kep = [r for r in last if r["source_record"]["procedure_id"] == "32616474682"]
    assert len(kep) == 2
    assert len({r["source_record"]["procedure_id"] for r in last}) == 2
    assert sum(float(r["metadata"]["nmck_rub"]) for r in kep) == 2452650.41
    assert {r["source_record"]["lot_number"] for r in kep} == {1, 2}
    assert all(r["metadata"]["winning_supplier_only_if_verified"] is None for r in last)
    assert all(r["metadata"]["original_primary_registry_verified"] is False for r in last)
    assert all(r["source_record"]["equipment_voltage_kv"] is None for r in last)
