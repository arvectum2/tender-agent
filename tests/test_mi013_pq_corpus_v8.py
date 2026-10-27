"""MI-013 v8: preserve previous corpus and append only grounded 6/10kV UDS cases."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "market_intelligence" / "power_quality"
SCRIPT = ROOT / "scripts" / "market_intelligence" / "materialize_pq_research.py"


def get_materializer():
    spec = importlib.util.spec_from_file_location("materialize_pq_research", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v8_procedure_corpus_preserves_58_records_and_produces_60_unique() -> None:
    old = json.loads((DATA / "verified_public_leads_20261027.v7.json").read_text())
    result = get_materializer().materialize()
    assert result["records"][:58] == old["records"]
    assert len(result["records"]) == 60
    assert len({r["canonical_id"] for r in result["records"]}) == 60
    assert result["verification_summary"]["added_records"] == 2
    assert result["seed_completeness"] == "discovered_examples_only_not_population"


def test_corporate_archive_dates_are_deadlines_and_no_winners_guessed() -> None:
    new = get_materializer().materialize()["records"][58:]
    assert {r["procedure_id"] for r in new} == {"5534/1866-УДСН", "5631/018-Ял"}
    assert {r["deadline_date"] for r in new} == {"2024-11-26", "2025-01-13"}
    assert all(r["publication_date"] is None for r in new)
    assert all(r["date_basis"] == "deadline_only_not_publication" for r in new)
    assert all(r["nmck_rub"] is None for r in new)
    assert all(r["quantity"] is None for r in new)
    assert all(r["evidence"][0]["url"].startswith("https://") for r in new)
    assert next(r for r in new if r["procedure_id"].startswith("5534"))["equipment_voltage_kv"] == 10
    assert next(r for r in new if r["procedure_id"].startswith("5631"))["equipment_voltage_kv_set"] == [6, 10]


def test_materializer_never_adds_context_as_procurements() -> None:
    corpus = get_materializer().materialize()
    context = json.loads((DATA / "market_context_20261027.v3.json").read_text())
    assert len(context["records"]) == 4
    assert all(x["id"] not in {r["id"] for r in corpus["records"]} for x in context["records"])
    assert corpus["data_version"] == "v8"
