"""Regression checks for sourced PQ market-intelligence corpus expansion (MI-013)."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "data/market_intelligence/power_quality"
V3 = ROOT / "verified_public_leads_20261027.v3.json"
V4 = ROOT / "verified_public_leads_20261027.v4.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_mi013_preserves_baseline_48_unchanged() -> None:
    prev, current = _read(V3), _read(V4)
    assert len(prev["records"]) == 48
    assert current["records"][:48] == prev["records"]
    assert len(current["records"]) == 54
    assert len({r["canonical_id"] for r in current["records"]}) == 54
    assert current["seed_completeness"] == "discovered_examples_only_not_population"


def test_mi013_added_six_have_grounded_sources_and_safe_money_types() -> None:
    records = _read(V4)["records"][48:]
    assert len(records) == 6
    expected = {"32515582393", "4535313", "4561228", "4561243", "4565274"}
    assert expected.issubset({r["procedure_id"] for r in records})
    for row in records:
        assert row["evidence"]
        assert all(
            e["url"].startswith("https://") and e["source_tier"] == "third_party"
            for e in row["evidence"]
        )
        assert row["nmck_rub"] is None or float(row["nmck_rub"]) > 0
        assert row.get("supplier_verified") is not True
        assert row.get("pq_equipment_only_contract_rub") is None
        assert row["scope"] in {"supply", "supply_candidate"}
    priced = [r for r in records if r["nmck_rub"] is not None]
    assert len(priced) == 1
    assert priced[0]["nmck_rub"] == "5880000"
    assert priced[0]["reported_price_kind"] == "initial_price_vat_included"


def test_mi013_repeat_demand_not_double_counted_as_awards() -> None:
    added = {r["procedure_id"]: r for r in _read(V4)["records"][48:] if r["procedure_id"]}
    assert added["4565274"]["explicit_replaces_procedure_id"] == "4538400"
    assert added["4565274"]["demand_group"] == added["4561228"]["demand_group"]
    assert added["4561243"]["demand_group"] != added["4561228"]["demand_group"]
    assert added["4535313"]["equipment_voltage_kv"] == 6
    assert added["4535313"]["equipment_reactive_power_mvar"] == 0.63
    summary = _read(V4)["verification_summary"]
    assert summary["prior_records"] == 48
    assert summary["added_records"] == 6
    assert summary["total_records"] == 54
    assert summary["added_contract_sum_verified_rub"] == "0"
