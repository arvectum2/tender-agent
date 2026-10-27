"""MI-013 v6: verified award-decision vendor is not automatically a signed-contract supplier."""

from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "data" / "market_intelligence" / "power_quality"


def load(v: int) -> dict:
    return json.loads((BASE / f"verified_public_leads_20261027.v{v}.json").read_text(encoding="utf-8"))


def test_v6_maintains_55_canonical_ids_and_changes_only_nagornaya() -> None:
    prior, current = load(5), load(6)
    a, b = prior["records"], current["records"]
    assert len(a) == len(b) == 55
    assert len({r["canonical_id"] for r in b}) == 55
    changes = [(p["procedure_id"], c["procedure_id"]) for p, c in zip(a, b) if p != c]
    assert changes == [("32615614821", "32615614821")]


def test_original_rd223_and_protocol_evidence_distinct_from_supplier_identity() -> None:
    d = load(6)
    row = next(r for r in d["records"] if r["procedure_id"] == "32615614821")
    assert row["nmck_rub"] == "1432983.66"
    assert row["registry_contract"]["signed_contract_registry_verified"] is True
    assert row["registry_contract"]["official_registered_total_rub"] == "1833358.30"
    assert row["registry_contract"]["registry_number"] == "50277071467260002650000"
    assert row["award_decision_vendor"] == "ООО «ТЕХНОПРОМ»"
    assert row["award_decision_original_protocol_verified"] is True
    assert row["supplier_identity_from_registry_verified"] is False
    assert row["supplier_verified"] is False
    assert row["pq_equipment_only_contract_rub"] is None
    assert row["equipment_voltage_kv"] == 6\n    assert row["equipment_reactive_power_mvar"] == 0.2
    assert sum(e["source_tier"] == "primary_platform" for e in row["evidence"]) >= 2
