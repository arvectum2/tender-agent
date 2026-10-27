"""MI-013 v10 must preserve 64 prior records and avoid duplicated power-system sales."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts/market_intelligence"
DATA = ROOT / "data/market_intelligence/power_quality"


def run_script(filename):
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / filename)], check=True,
        capture_output=True, text=True, timeout=35
    )
    return json.loads(r.stdout)


def test_v10_append_only_preserves_v9_and_unique_keys():
    before = run_script("materialize_pq_research_v9.py")
    after = run_script("materialize_pq_research_v10.py")
    assert len(before["records"]) == 64
    assert len(after["records"]) == 68
    assert after["records"][:64] == before["records"]
    assert len({r["canonical_id"] for r in after["records"]}) == 68
    assert after["seed_completeness"] == "discovered_examples_only_not_population"


def test_v10_ufimka_contracted_epc_not_equipment_sale():
    rows = run_script("materialize_pq_research_v10.py")["records"][64:]
    r = next(x for x in rows if x["procedure_id"] == "32514476448")
    assert r["equipment_voltage_kv"] == 10
    assert r["equipment_reactive_power_mvar_total"] == 1.8
    assert r["nmck_rub"] == "3176527.55"
    assert r["linked_contract_registry_number"] == "50277071467250001900000"
    assert r["reported_contract_total_rub"] == "2922405.35"
    assert r["reported_contract_total_source_tier"].startswith("third_party")
    assert r["supplier_verified"] is False
    assert r["pq_equipment_only_contract_rub"] is None


def test_v10_tyazhinskaya_links_same_demand_across_years():
    rows = run_script("materialize_pq_research_v10.py")["records"][64:]
    design = [r for r in rows if r["demand_group"] == "TYAZHINSKAYA-BSK110-TO-SKRM52-DESIGN-2025-26"]
    assert {r["procedure_id"] for r in design} == {"32515044454", "32616354211"}
    assert len({r["demand_group"] for r in design}) == 1
    for r in design:
        assert r["scope"] == "design"
        assert r["equipment_voltage_kv"] is None
        assert r["equipment_reactive_power_mvar_total"] == 52
        assert r["pq_equipment_only_contract_rub"] is None
        assert r["supplier_verified"] is False
    assert {r["nmck_rub"] for r in design} == {"3031988", "7519646.09"}
    proc = next(r for r in design if r["procedure_id"] == "32616354211")
    assert proc["reported_contract_total_rub"] == "7406851.40"
    assert proc["reported_contract_total_source_tier"].startswith("third_party")
    assert proc["linked_contract_registry_number"] is None


def test_v10_noncanonical_april_2026_index_not_counted_as_procurement():
    delta = json.loads((DATA / "rosseti_bashkirenergo_2025_26_project_chain_delta.json").read_text())
    assert len(delta["non_procurement_related_index"]) == 1
    assert delta["non_procurement_related_index"][0]["indexed_id"] == "tenderguru:93843219"
    assert len(delta["records"]) == 4


def test_v10_pogranichnaya_is_commercial_bsk35_and_unknown_price():
    r = next(r for r in run_script("materialize_pq_research_v10.py")["records"] if r["procedure_id"] == "RAD260049805")
    assert r["canonical_id"] == "commercial:RAD260049805:lot1"
    assert r["procurement_regime"] == "commercial"
    assert r["equipment_voltage_kv"] == 35
    assert r["family"] == "capacitor_bank"
    assert r["scope"] == "epc"
    assert r["nmck_rub"] is None
    assert r["quantity"] == 1
    assert r["supplier_verified"] is False
    assert r["reported_contract_total_rub"] is None
    assert r["pq_equipment_only_contract_rub"] is None
