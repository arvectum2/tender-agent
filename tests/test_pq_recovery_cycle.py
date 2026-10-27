from pathlib import Path
from unittest.mock import patch

import pytest

from src.modules.market_intelligence.pq_recovery_cycle import run_cycle


def test_offline_cycle_is_bounded_and_persists(tmp_path: Path):
    runtime = tmp_path / "runtime"
    with patch("src.modules.market_intelligence.pq_recovery_cycle.inventory",
               return_value={"lead_count": 1}), patch(
        "src.modules.market_intelligence.pq_recovery_cycle.seed",
        return_value={"created": []}) as queue:
        source = tmp_path / "sources"
        source.mkdir()
        result = run_cycle(leads=tmp_path / "leads.json", source_roots=[source],
                           archive_index=tmp_path / "index.json",
                           runtime=runtime, ontology=tmp_path / "ontology.yaml",
                           dp_source=tmp_path / "dp", network=False)
    assert result["official_search"]["status"] == "skipped_offline"
    assert result["indexed_recovery"]["status"] == "skipped_offline"
    assert result["data_platform"]["files_inspected"] == 0
    assert queue.call_count == 1
    assert (runtime / "last-recovery-cycle.json").is_file()


def test_cycle_budget_validation(tmp_path: Path):
    with pytest.raises(ValueError):
        run_cycle(leads=tmp_path / "leads", source_roots=[],
                  archive_index=tmp_path / "index", runtime=tmp_path,
                  ontology=tmp_path / "ontology", dp_source=tmp_path,
                  max_cases=0)


def test_verified_manifests_do_not_shrink_with_network_batch(tmp_path: Path):
    """Changing live-search quantum must not invalidate verified ZIP cursor."""
    source = tmp_path / "sources"
    source.mkdir()
    with patch("src.modules.market_intelligence.pq_recovery_cycle.inventory",
               return_value={"lead_count": 100}), patch(
        "src.modules.market_intelligence.pq_recovery_cycle.stage",
        return_value={"files_staged": 19}) as stage, patch(
        "src.modules.market_intelligence.pq_recovery_cycle.expand",
        return_value={"members_staged": 64}) as expand, patch(
        "src.modules.market_intelligence.pq_recovery_cycle.seed",
        return_value={"created": []}), patch(
        "src.modules.market_intelligence.pq_recovery_cycle.ingest",
        return_value={"files_inspected": 0}), patch(
        "src.modules.market_intelligence.pq_recovery_cycle.resume_zip_ingest",
        return_value={"status": "complete"}):
        run_cycle(leads=tmp_path / "leads.json", source_roots=[source],
                  archive_index=tmp_path / "index.json", runtime=tmp_path / "runtime",
                  ontology=tmp_path / "ontology.yaml", dp_source=tmp_path / "dp",
                  max_cases=2, network=False, verified_reestr=tmp_path / "reestr")
    assert stage.call_args.kwargs["max_cases"] == 100
    assert expand.call_args.kwargs["max_cases"] == 100


def test_verified_source_budget_validation(tmp_path: Path):
    source = tmp_path / "sources"
    source.mkdir()
    with pytest.raises(ValueError, match="Invalid cycle scope"):
        run_cycle(leads=tmp_path / "leads.json", source_roots=[source],
                  archive_index=tmp_path / "index.json", runtime=tmp_path / "runtime",
                  ontology=tmp_path / "ontology.yaml", dp_source=tmp_path / "dp",
                  verified_max_cases=0)
