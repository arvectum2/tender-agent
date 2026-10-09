"""Regression protecting the admitted APR-02 outcome boundary."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_apr02_bounded_outcome_and_queue_are_consistent():
    roadmap = yaml.safe_load((ROOT / "docs/roadmap/master-roadmap.yaml").read_text())
    outcomes = roadmap["active_product_roadmap_2026_10_08"]["outcomes"]
    apr02 = next(x for x in outcomes if x["id"] == "APR-02-223FZ-BREADTH")
    assert apr02["state"] == "done"
    assert apr02["universal_223fz_coverage"] == "not_claimed"
    assert apr02["local_model_comparison"] == "deferred_to_APR_07"

    report = ROOT / apr02["completion_evidence"]
    assert report.is_file()
    content = report.read_text()
    assert "UNKNOWN/UNVERIFIED" in content
    assert "32616376947" in content
    assert "32616445795" in content
    assert "19 original RAR files" in content

    queue = yaml.safe_load((ROOT / ".agent/execution-queue.yaml").read_text())
    admitted = [
        row
        for row in queue["items"]
        if str(row.get("task_id", "")).startswith("APR-02-")
    ]
    assert admitted
    assert all(row["status"] == "done" for row in admitted)
