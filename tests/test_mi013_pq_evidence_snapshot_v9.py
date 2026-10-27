"""MI-013 v9 evidence snapshot cross-checks exact source-delta arithmetic."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data/market_intelligence/power_quality"

def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_v9_evidence_counts_and_money_types():
    previous = load("evidence_quality_snapshot_20261027.v8.json")
    current = load("evidence_quality_snapshot_20261027.v9.json")
    delta = load("rosseti_2025_pq_components_epc_delta.json")
    assert len(delta["records"]) == 4
    assert previous["procurement_records"] == 60
    assert current["procurement_records"] == 64
    assert current["canonical_ids_unique"] == 64
    assert current["regime_counts"]["223-fz"] == previous["regime_counts"]["223-fz"] + 4
    assert current["regime_counts"]["commercial"] == 45
    assert current["nmck_any_non_null_count"] == previous["nmck_any_non_null_count"] + 4
    assert current["records_with_primary_platform_evidence_count"] == 11
    assert current["registered_contract_primary_verified_count"] == 4
    assert sum(int(r["nmck_rub"]) for r in delta["records"]) == 90672176
    assert current["added_nmck_sum_rub_not_market_value"] == "90672176"
    for row in delta["records"]:
        assert row["reported_price_kind"] == "initial_price_not_contract"
        assert row["equipment_voltage_kv"] is None
        assert row["award_winner_verified"] is False
        assert row["registered_contract_verified"] is False
        assert row["official_tz_verified"] is False


def test_v9_does_not_infer_pq_market_sales_from_mixed_epc():
    quality = load("evidence_quality_snapshot_20261027.v9.json")
    assert "NOT TOTAL RUSSIAN MARKET SIZE" in quality["description"]
    assert "NOT total PQ equipment sales" in quality["caveat"]
    assert sum(quality["family_counts"].values()) == 64
    assert sum(quality["scope_counts"].values()) == 64
    assert sum(quality["regime_counts"].values()) == 64
