"""MI-013 v8 evidence quality checks across base JSON and archived corporate delta."""

import json
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data/market_intelligence/power_quality"


def read(filename):
    return json.loads((DATA / filename).read_text(encoding="utf-8"))


def test_v8_statistical_denominators():
    base = read("verified_public_leads_20261027.v7.json")["records"]
    new = read("udsgroup_archive_2024_2025.json")["records"]
    quality = read("evidence_quality_snapshot_20261027.v8.json")
    assert len(base) == 58
    assert len(new) == 2
    assert quality["procurement_records"] == 60
    assert len({r["canonical_id"] for r in base + new}) == 60
    regime = Counter(r["procurement_regime"] for r in base)
    regime["commercial"] += len(new)
    assert dict(regime) == quality["regime_counts"]
    assert quality["nmck_any_non_null_count"] == sum(r["nmck_rub"] is not None for r in base)
    assert quality["registered_contract_primary_verified_count"] == sum(
        r.get("registry_contract", {}).get("signed_contract_registry_verified") is True
        for r in base
    )
    assert quality["context_nonprocurement_records"] == len(
        read("market_context_20261027.v3.json")["records"]
    ) == 4


def test_v8_archive_does_not_claim_awards():
    quality = read("evidence_quality_snapshot_20261027.v8.json")
    new = read("udsgroup_archive_2024_2025.json")["records"]
    assert "NOT TOTAL RUSSIAN MARKET SIZE" in quality["description"]
    assert all(x["publication_date"] is None for x in new)
    assert all(x["winner"] is None and x["contract_rub"] is None for x in new)
