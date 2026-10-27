"""Source-bound regression for append-only 2026-10-27 Power Quality research."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/market_intelligence/power_quality/verified_public_leads_20261025.v2.json"
LATEST = ROOT / "data/market_intelligence/power_quality/verified_public_leads_20261027.v3.json"
RD223 = ROOT / "data/market_intelligence/power_quality/official_registry_contracts_20261026.v1.json"


def test_mi013_v3_preserves_45_previous_discovery_records():
    old = json.loads(BASE.read_text(encoding="utf-8"))
    new = json.loads(LATEST.read_text(encoding="utf-8"))
    assert len(old["records"]) == 45
    assert len(new["records"]) == 48
    assert new["records"][:45] == old["records"]
    canonical = [r["canonical_id"] for r in new["records"]]
    assert len(set(canonical)) == 48
    assert set(canonical[45:]) == {
        "223fz:32615852898:lot1",
        "commercial:UKK-0SCS-3-102:lot1",
        "commercial:111098-ТТ:lot1",
    }


def test_mi013_v3_does_not_infer_equipment_sales_from_mixed_work():
    latest = json.loads(LATEST.read_text(encoding="utf-8"))
    added = {r["procedure_id"]: r for r in latest["records"][45:]}
    sosnovskaya = added["32615852898"]
    assert sosnovskaya["nmck_rub"] == "2950502.46"
    assert sosnovskaya["reported_contract_total_rub"] == "2787700.00"
    assert sosnovskaya["supplier_verified"] is False
    assert sosnovskaya["pq_equipment_only_contract_rub"] is None
    assert "not_verified_original" in sosnovskaya["reported_contract_total_source_tier"]
    eurochem = added["UKK-0SCS-3-102"]
    assert eurochem["scope"] == "adjacent_epc"
    assert eurochem["nmck_rub"] is None
    assert "Нельзя считать напряжением ФКУ" in eurochem["notes"]
    gaysky = added["111098-ТТ"]
    assert gaysky["reissue_group"] == "GAY-GOK-UKRM-600-REPEAT"
    assert len(gaysky["potential_same_demand_as"]) == 2


def test_mi013_v3_preserves_primary_angarsk_contract_over_secondary_bid():
    official = json.loads(RD223.read_text(encoding="utf-8"))
    matches = [x for x in official["contracts"] if x["contract_latest"]["linked_procurement"] == "32616412267"]
    assert len(matches) == 1
    case = matches[0]["contract_latest"]
    assert case["registered_total_price_rub"] == "2639026.64"
    assert case["supplier_identity_from_registry_verified"] is False
    assert case["pq_equipment_sale_rub"] is None
