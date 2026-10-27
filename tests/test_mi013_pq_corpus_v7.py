"""Cross-version MI-013 checks: procurement records, market context and evidence tiers."""

from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "data/market_intelligence/power_quality"


def load(filename: str) -> dict:
    return json.loads((BASE / filename).read_text(encoding="utf-8"))


def test_v7_preserves_v6_and_adds_three_nonduplicated_procurement_ids() -> None:
    previous = load("verified_public_leads_20261027.v6.json")
    current = load("verified_public_leads_20261027.v7.json")
    assert current["records"][:55] == previous["records"]
    rows = current["records"]
    assert len(rows) == 58
    assert len({r["canonical_id"] for r in rows}) == 58
    new = rows[55:]
    assert {r["procedure_id"] for r in new} == {"ГП630876", "32515218366", "5747901"}
    assert all(r["evidence"] for r in new)
    assert all(all(e["url"].startswith("https://") for e in r["evidence"]) for r in new)


def test_v7_no_spurious_sales_figures_and_known_voltage_isolated() -> None:
    rows = load("verified_public_leads_20261027.v7.json")["records"][55:]
    novatek = next(r for r in rows if r["procedure_id"] == "ГП630876")
    assert novatek["equipment_voltage_kv"] == 10
    assert novatek["nmck_rub"] is None
    assert novatek["market_scope"].startswith("strict_6_35kv")
    ntc = next(r for r in rows if r["procedure_id"] == "32515218366")
    assert ntc["nmck_rub"] == "49900000"
    assert ntc["reported_price_kind"] == "initial_price_vat_included"
    assert ntc["market_scope"] == "adjacent_upstream_components_not_strict_6_35_kv"
    elbrus = next(r for r in rows if r["procedure_id"] == "5747901")
    assert elbrus["market_scope"] == "voltage_unconfirmed_pending_TZ"
    assert "4158439" in elbrus["potential_related_procedure_ids"]
    assert all(r.get("reported_contract_total_rub") is None for r in rows)
    assert all(r.get("supplier_verified") is not True for r in rows)


def test_context_separated_and_no_plans_as_signed_contracts() -> None:
    context = load("market_context_20261027.json")["records"]
    assert len(context) == 3
    assert len({r["id"] for r in context}) == 3
    assert {r["kind"] for r in context} == {
        "commissioned_reference", "procurement_plan_not_notice",
        "supplier_award_aggregator_unmatched_date",
    }
    rosseti = next(r for r in context if r["kind"] == "procurement_plan_not_notice")
    assert rosseti["planned_value_rub"] == "41730480"
    assert rosseti["actual_contract_total_rub"] is None
    assert rosseti["procurement_number"] is None
    assert rosseti["equipment"][0]["voltage_kv"] is None
    erasib = next(r for r in context if r["kind"] == "commissioned_reference")
    assert len(erasib["equipment"]) == 2
    assert erasib["equipment"][0]["reactive_compensation_kvar"] == 885
    assert erasib["equipment"][1]["reported_compensation_range_kvar"] == "±2000"
    assert erasib["contract_total_rub"] is None
    vendor = next(r for r in context if r["kind"] == "supplier_award_aggregator_unmatched_date")
    assert vendor["event_date"] is None and vendor["procurement_number"] is None
    assert vendor["reported_award_total_rub"] == "293080"
