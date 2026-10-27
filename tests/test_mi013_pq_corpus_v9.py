"""Regression for four newly indexed Rosseti 2025 PQ source leads (v9)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "market_intelligence"
DATA = ROOT / "data" / "market_intelligence" / "power_quality"


def load_materializer():
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("pq_v9_materializer", SCRIPTS / "materialize_pq_research_v9.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.materialize()
    finally:
        sys.path.remove(str(SCRIPTS))


def test_v9_preserves_v8_and_has_64_unique_research_leads():
    from subprocess import run
    import sys as interpreter
    r8 = run([interpreter.executable, str(SCRIPTS / "materialize_pq_research.py")], capture_output=True, text=True, check=True)
    prior = json.loads(r8.stdout)
    v9 = load_materializer()
    assert len(prior["records"]) == 60
    assert v9["records"][:60] == prior["records"]
    assert len(v9["records"]) == 64
    assert len({r["canonical_id"] for r in v9["records"]}) == 64
    assert v9["seed_completeness"] == "discovered_examples_only_not_population"


def test_v9_financial_and_technical_uncertainty_is_preserved():
    rows = load_materializer()["records"][60:]
    assert {r["procedure_id"] for r in rows} == {
        "32515029641", "32514947144", "32515225588", "32515208744"
    }
    assert {r["scope"] for r in rows} == {"supply_components", "design", "epc"}
    assert sum(int(r["nmck_rub"]) for r in rows) == 90672176
    for r in rows:
        assert r["equipment_voltage_kv"] is None
        assert r["pq_equipment_only_contract_rub"] is None
        assert r["supplier_verified"] is False
        assert r["reported_contract_total_rub"] is None
        assert r["reported_price_kind"] == "initial_price_not_contract"
        assert r["evidence"][0]["url"].startswith("https://")
    assert all(r["family"] == "harmonic_filter" for r in rows[:2])
