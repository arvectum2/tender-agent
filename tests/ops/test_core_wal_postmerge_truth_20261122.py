"""Guard verified Code/PG17 WAL completion versus unaccepted product release."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf8"))


def test_three_core_pr_merges_close_only_engineering_consolidation():
    index = _read(".agent/current-task.yaml")
    current = index["parallel_core_consolidation"]
    checkpoint = _read(current["checkpoint"])
    assert current["status"] == checkpoint["status"] == "completed"
    assert checkpoint["remaining"] == []
    assert checkpoint["pr529_merge_sha"] == "78be86422aab7cc7b5a869f45d431847c5551a61"
    assert checkpoint["pr530_merge_sha"] == "4e801b8f5e1710caac8fbf703596383aa3ba389d"
    assert checkpoint["pr531_merge_sha"] == "35c44a898b56c055bbcd50a8be25227459c08e58"
    for n in (529, 530, 531):
        assert checkpoint[f"pr{n}_ci"] == "19_of_19_success"
    assert checkpoint["production_deployed"] is False
    assert _read(".agent/checkpoints/TA-CORE-RUNTIME-PACKAGING-20261115.yaml")["status"] == "completed"


def test_runtime_switch_stays_blocked_on_owner_and_DP():
    index = _read(".agent/current-task.yaml")
    gate = index["core_runtime_release_2026_11_22"]
    child = _read(gate["checkpoint"])
    assert gate["status"] == child["status"] == "blocked"
    assert gate["production_deployed"] is child["production_deployed"] is False
    assert "owner_exact_release_approval" in child["remaining"]
    assert "live_DP_HTTP_and_SDK_reliability" in child["remaining"]
    assert "authorized_runtime_deploy" in child["remaining"]


def test_pg17_record_integrity_proven_without_seven_day_pitr():
    index = _read(".agent/current-task.yaml")
    completed = index["pitr_wal_content_integrity_2026_11_22"]
    child = _read(completed["checkpoint"])
    assert completed["status"] == child["status"] == "completed"
    assert child["remaining"] == []
    assert child["protected_merge_commit"] == "aed8ef80d2ba3bad7b3c8016473b3228550f3c6d"
    assert child["protected_exact_ci"] == "10_of_10_success"
    assert child["seven_day_pitr_proven"] is False
    assert child["production_deployed"] is False
    future = index["pitr_seven_day_2026_11_22"]
    pending = _read(future["checkpoint"])
    assert future["status"] == pending["status"] == "blocked"
    assert "exact_seven_day_restore" in pending["remaining"]
    assert index["status"] == "in_progress"


def test_execution_queue_does_not_advance_unreviewed_commercial_forecast():
    items = _read(".agent/execution-queue.yaml")["items"]
    assert len(items) == 66 and sum(x["status"] == "done" for x in items) == 65
    assert [(x["task_id"], x["status"], x["authority"]) for x in items
            if x["status"] != "done"] == [
                ("COMMERCIAL-WORKFLOW-ARV-069-001", "blocked", "REVIEW")
            ]
