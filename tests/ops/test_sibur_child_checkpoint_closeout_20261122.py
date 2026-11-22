"""Verify merged source-only SIBUR children without treating source gaps as GO."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / ".agent/current-task.yaml"
QUEUE = ROOT / ".agent/execution-queue.yaml"

DONE = {
    "sibur_ppt_source_forensic_2026_11_22": (
        "TA-SIBUR-PPT-SOURCE-FORENSIC-20261122",
        705,
        "664e3283aed9dabafdda9de4d0f8405f085ffa6e",
    ),
    "sibur_import_window_2026_11_22": (
        "TA-SIBUR-IMPORT-WINDOW-20261122",
        706,
        "755a56a4059a91e77b84059fbc7ed286ef48c49d",
    ),
}


def test_ppt_and_import_are_completed_bounded_engineering_work():
    parent = yaml.safe_load(CURRENT.read_text(encoding="utf8"))
    for key, (task_id, pr, merge) in DONE.items():
        entry = parent[key]
        checkpoint = yaml.safe_load(
            (ROOT / entry["checkpoint"]).read_text(encoding="utf8")
        )
        assert entry["status"] == checkpoint["status"] == "completed"
        assert entry["task_id"] == checkpoint["task_id"] == task_id
        assert checkpoint["protected_pr"] == pr
        assert checkpoint["protected_merge_commit"] == merge
        assert checkpoint["protected_exact_ci"] == "19_of_19_success"
        assert checkpoint["remaining"] == []
        assert checkpoint["production_mutations"] is False


def test_unattested_originals_and_seven_day_pitr_stay_blocked():
    parent = yaml.safe_load(CURRENT.read_text(encoding="utf8"))
    assert parent["status"] == "in_progress"
    assert parent["dtr679_current_originals_2026_11_22"]["status"] == "blocked"
    assert parent["pitr_seven_day_2026_11_22"]["status"] == "blocked"
    ppt = yaml.safe_load(
        (ROOT / parent["sibur_ppt_source_forensic_2026_11_22"]["checkpoint"]).read_text()
    )
    assert ppt["linked_issue"] == 686
    assert "cf3f16c5cde02cde9589cd3c4b41ca02c5cec39140743005c9b2a39617c1dc3c" in (
        str(ppt["completed"])
    )


def test_no_mass_import_or_open_now_claim_from_closure():
    import_check = yaml.safe_load(
        (ROOT / ".agent/checkpoints/TA-SIBUR-IMPORT-WINDOW-20261122.yaml").read_text()
    )
    assert import_check["linked_issue"] == 692
    assert "2e51b08c9e4c40d245a015a1317aa5cef600da07ca41d13c973b0a8617b220fc" in (
        str(import_check["completed"])
    )
    queue = yaml.safe_load(QUEUE.read_text(encoding="utf8"))["items"]
    assert len(queue) == 66
    assert sum(x["status"] == "done" for x in queue) == 65
    remaining = [x for x in queue if x["status"] != "done"]
    assert len(remaining) == 1
    assert (remaining[0]["task_id"], remaining[0]["status"], remaining[0]["authority"]) == (
        "COMMERCIAL-WORKFLOW-ARV-069-001", "blocked", "REVIEW",
    )
