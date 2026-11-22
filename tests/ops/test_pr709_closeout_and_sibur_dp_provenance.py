"""Checkpoint of exact protected PR709 status and fail-closed SIBUR DP scope."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _read(relative):
    return yaml.safe_load((ROOT / relative).read_text(encoding="utf8"))


def test_completed_pr709_has_exact_protected_merge_proof():
    current = _read(".agent/current-task.yaml")
    entry = current["postmerge_truth_2026_11_22"]
    checkpoint = _read(entry["checkpoint"])
    assert entry["status"] == checkpoint["status"] == "completed"
    assert checkpoint["remaining"] == []
    assert checkpoint["protected_merge_commit"] == "faba2e775fde8d504e9d66d46434f2eccd10879d"
    assert checkpoint["protected_exact_ci"] == "10_of_10_success"
    assert checkpoint["production_mutations"] is False


def test_seven_sibur_original_proof_does_not_promote_live_dp_or_source():
    current = _read(".agent/current-task.yaml")
    entry = current["sibur_dp_source_provenance_2026_11_22"]
    child = _read(entry["checkpoint"])
    assert child["task_id"] == entry["task_id"]
    assert entry["status"] in ("in_progress", "completed")
    assert entry["production_mutations"] is False
    assert entry["live_dp_index_verified"] is False
    assert child["full_historical_DP_source_lineage_proven"] == 7
    assert child["source_current_status_verified"] is False
    assert child["live_DP_state_verified"] is False
