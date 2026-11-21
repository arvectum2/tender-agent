"""Separate original equipment price benchmark from services, contract and sales."""
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path


def test_meles_first_party_originals_are_exact_and_role_gated():
    p = (Path(__file__).resolve().parents[1] / "docs/market_intelligence"
         / "PQ_MELEUZ_6KV_SOURCE_REVALIDATION_20261029.json")
    obj = json.loads(p.read_text(encoding="utf-8"))
    assert obj["canonical_id"] == "223fz:32616296475:lot1"
    assert obj["new_tender_count_added"] == 0
    assert len(obj["original_sources"]) == 3
    assert all(source["http_status"] == 200 and source["original_sha_reverified"]
               and len(source["sha256"]) == 64 for source in obj["original_sources"])
    tech = obj["technology"]
    assert tech["network_bus_kv"] == 6
    assert tech["min_reactive_power_kvar"] == 500
    assert "not_proven" in tech["fgi_svg_equivalence"]
    price = obj["buyer_price_justification"]
    vals = [Decimal(value) for value in price["equipment_only_quotes_rub"]]
    average = (sum(vals) / Decimal(3)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    assert average == Decimal(price["equipment_only_arithmetic_average_rub"])
    assert average + Decimal(price["separate_installation_services_average_rub"]) == Decimal(
        price["total_initial_NMCD_rub"]
    )
    assert obj["original_contract_template"]["source_is_draft_not_signed"]
    assert obj["original_contract_template"]["party_name_left_blank"]
    assert obj["signed_supplier_verified"] is False
    assert obj["actual_signed_equipment_revenue_rub"] is None
    assert obj["national_market_value_contribution_rub"] == 0
