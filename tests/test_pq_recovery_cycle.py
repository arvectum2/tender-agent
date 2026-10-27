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


def test_cycle_contract_register_stage(tmp_path: Path):
    source = tmp_path / "originals"
    source.mkdir()
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    runtime = tmp_path / "runtime"
    with patch("src.modules.market_intelligence.pq_recovery_cycle.inventory",
               return_value={"lead_count": 2}), patch(
        "src.modules.market_intelligence.pq_recovery_cycle.seed",
        return_value={"created": []}), patch(
        "src.modules.market_intelligence.pq_recovery_cycle.scan_contracts",
        return_value={"records": [], "distinct_contract_lots": 0}) as scan, patch(
        "src.modules.market_intelligence.pq_recovery_cycle.audit_contracts",
        return_value={"distinct_contract_lots_matched": 0,
                      "contract_lots_with_rub_price": 0,
                      "signed_contracts_verified": 0,
                      "suppliers_verified": 0, "records": []}) as audit:
        result = run_cycle(leads=tmp_path / "leads.json", source_roots=[source],
                           archive_index=tmp_path / "index.json",
                           runtime=runtime, ontology=tmp_path / "ontology.yaml",
                           dp_source=tmp_path / "dp", network=False,
                           contract_root=contracts)
    assert scan.call_count == 1
    assert audit.call_count == 1
    assert result["contract_register"]["records_matched"] == 0
    assert (runtime / "contract-xml-evidence.json").exists()
    assert (runtime / "contract-outcome-audit.json").exists()
    assert (runtime / "commission-candidates.json").exists()
    assert result["commission_candidates"]["supplier_verified"] == 0
