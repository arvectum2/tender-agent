"""Regression validation for MI-013 v5 incremental procurement intelligence."""

from __future__ import annotations

import json
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "data/market_intelligence/power_quality"


def _read(version: int) -> dict:
    return json.loads((DATA / f"verified_public_leads_20261027.v{version}.json").read_text(encoding="utf-8"))


def test_v5_preserves_v4_and_55_unique_procedures() -> None:
    baseline, current = _read(4), _read(5)
    assert len(baseline["records"]) == 54
    assert current["records"][:54] == baseline["records"]
    assert len(current["records"]) == 55
    assert len({r["canonical_id"] for r in current["records"]}) == 55
    assert current["seed_completeness"] == "discovered_examples_only_not_population"


def test_meleuz_financial_and_award_provenance_not_overstated() -> None:
    r = _read(5)["records"][-1]
    assert r["procedure_id"] == "32616296475"
    assert r["procurement_regime"] == "223-fz"
    assert r["customer"]["inn"] == "0263017332"
    assert r["nmck_rub"] == "3904773.73"
    assert r["reported_price_kind"] == "initial_price"
    assert r["equipment_voltage_kv"] is None
    assert r["supplier_verified"] is False
    assert r["supplier_inn"] is None
    assert r["reported_contract_total_rub"] is None
    assert r["pq_equipment_only_contract_rub"] is None
    assert r["market_scope"] == "voltage_unconfirmed_not_counted_in_strict_6_35_kV"
    assert len(r["evidence"]) >= 2
    assert all(e["source_tier"] == "third_party" and e["url"].startswith("https://") for e in r["evidence"])
    summary = _read(5)["verification_summary"]
    assert summary["total_records"] == 55
    assert summary["added_initial_price_rub"] == "3904773.73"
    assert summary["added_contract_sum_verified_rub"] == "0"
