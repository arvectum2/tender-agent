"""Regression contract for completed source inventories and held hard stops."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf8"))


def test_three_source_discoveries_are_done_in_order_without_priority_change():
    queue = load(".agent/execution-queue.yaml")
    items = queue["items"]
    ids = [
        "TA-SIBUR-SOURCE-DISCOVERY-001",
        "TA-GEH-SOURCE-DISCOVERY-001",
        "TA-AI-TRADING-SOURCE-DISCOVERY-001",
    ]
    typed = {item["task_id"]: item for item in items}
    assert [typed[name]["order"] for name in ids] == [1130, 1140, 1150]
    assert all(typed[name]["status"] == "done" for name in ids)
    assert all(typed[name]["authority"] == "AUTO" for name in ids)
    assert sum(item["status"] == "done" for item in items) == 65
    open_items = [item for item in items if item["status"] != "done"]
    assert [(item["task_id"], item["status"], item["authority"]) for item in open_items] == [
        ("COMMERCIAL-WORKFLOW-ARV-069-001", "blocked", "REVIEW")
    ]


def test_child_checkpoint_done_requires_nonempty_merge_evidence():
    parent = load(".agent/current-task.yaml")
    names = {
        "roadmap_reconciliation_2026_11_22": "TA-ROADMAP-RECONCILE-20261122",
        "sibur_source_discovery_2026_11_22": "TA-SIBUR-SOURCE-DISCOVERY-001",
        "geh_source_discovery_2026_11_22": "TA-GEH-SOURCE-DISCOVERY-001",
        "ai_trading_source_discovery_2026_11_22": "TA-AI-TRADING-SOURCE-DISCOVERY-001",
    }
    for key, task_id in names.items():
        metadata = parent[key]
        child = load(metadata["checkpoint"])
        assert metadata["task_id"] == child["task_id"] == task_id
        assert metadata["status"] == child["status"] == "completed"
        assert child["remaining"] == []
        merge = child["protected_merge_commit"]
        assert isinstance(merge, str) and len(merge) == 40
        assert child["protected_exact_ci"] == "19_of_19_success"
        assert child["production_deployed"] is False
    assert parent["status"] == "in_progress"


def test_unresolved_sibur_historical_gap_issues_not_falsely_closed():
    parent = load(".agent/current-task.yaml")
    gap = parent["sibur_gap_readonly_2026_11_22"]
    child = load(gap["checkpoint"])
    assert gap["status"] == child["status"] == "completed"
    assert child["linked_issue"] == 692
    assert child["issue_692_root_cause"] == "UNKNOWN"
    assert child["historic_mass_import_authorized"] is False
    assert child["private_exact_working_gap_sha256"] == (
        "4dae9e36df79dbbf678fab5264a4e60de378d71fd391e8b7d7e71280e39151a8"
    )
    for key in ["dtr679_current_originals_2026_11_22",
                "pitr_seven_day_2026_11_22"]:
        assert parent[key]["status"] == "blocked"
    assert parent["pitr_exact_wal_2026_11_22"]["status"] == "completed"


def test_paper_trading_and_live_connector_remain_nonoperational():
    import json

    sibur = json.loads(
        (ROOT / "docs/roadmap/ta_sibur_source_reuse_inventory_20261122.json").read_text()
    )
    geh = json.loads(
        (ROOT / "docs/roadmap/ta_geh_source_reuse_inventory_20261122.json").read_text()
    )
    paper = json.loads(
        (ROOT / "docs/roadmap/ta_ai_trading_source_reuse_inventory_20261122.json").read_text()
    )
    assert sibur["authorized_srm_session"] is False
    assert geh["live_platform_api_verified"] is False
    assert paper["mode"] == "PAPER_SIMULATION_ONLY"
    assert paper["real_bid_allowed"] is paper["real_order_allowed"] is False
    assert paper["sample_proof"]["simulated_bids_run"] == 0
    assert paper["sample_proof"]["automation_percent_measured"] is False
