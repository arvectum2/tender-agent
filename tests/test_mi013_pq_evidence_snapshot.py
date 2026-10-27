"""Evidence-denominator quality snapshot: no sampling statistics misreported as market volume."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data/market_intelligence/power_quality"


def read(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_mi013_snapshot_denominators_recomputed_from_v7() -> None:
    d = read("verified_public_leads_20261027.v7.json")
    rows = d["records"]
    snap = read("evidence_quality_snapshot_20261027.json")
    assert snap["procurement_records"] == len(rows) == 58
    assert snap["canonical_ids_unique"] == len({r["canonical_id"] for r in rows}) == 58
    assert snap["nmck_any_non_null_count"] == sum(r["nmck_rub"] is not None for r in rows)
    assert snap["explicit_structured_voltage_6_to_35_kv_count"] == sum(
        isinstance(r.get("equipment_voltage_kv"), (int, float))
        and 6 <= r["equipment_voltage_kv"] <= 35 for r in rows
    )
    assert snap["with_primary_platform_evidence_count"] == sum(
        any(e["source_tier"] == "primary_platform" for e in r["evidence"])
        for r in rows
    )
    assert snap["registered_contract_primary_verified_count"] == sum(
        r.get("registry_contract", {}).get("signed_contract_registry_verified") is True
        for r in rows
    )
    assert sum(snap["regime_counts"].values()) == snap["procurement_records"]
    assert sum(snap["family_counts"].values()) == snap["procurement_records"]
    assert sum(snap["scope_counts"].values()) == snap["procurement_records"]


def test_quality_snapshot_explicitly_rejects_market_share_inferences() -> None:
    s = read("evidence_quality_snapshot_20261027.json")
    assert "NOT MARKET SIZING" in s["description"]
    assert "not real PQ market share" in s["metrics_caveat"]
    assert s["regime_counts"] == {"223-fz": 15, "commercial": 43}
    assert s["registered_contract_primary_verified_count"] == 4
    assert s["contextual_non_procurement_records"] == 3
