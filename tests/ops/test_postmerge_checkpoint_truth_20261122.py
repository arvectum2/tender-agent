"""Guard source-only postmerge completion versus unresolved live acceptance."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / ".agent/current-task.yaml"


def _load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf8"))


def test_unique_parent_keys_and_completed_ci_child_proofs():
    node = yaml.compose(CURRENT.read_text(encoding="utf8"))

    def scan(value, prefix="root"):
        if isinstance(value, yaml.MappingNode):
            existing = set()
            for key, child in value.value:
                assert key.value not in existing, f"duplicate {prefix}/{key.value}"
                existing.add(key.value)
                scan(child, prefix + "/" + key.value)
        if isinstance(value, yaml.SequenceNode):
            for child in value.value:
                scan(child, prefix)

    scan(node)
    current = _load(CURRENT)
    merges = {
        "sibur_ppt_source_forensic_2026_11_22": "664e3283aed9dabafdda9de4d0f8405f085ffa6e",
        "sibur_import_window_2026_11_22": "755a56a4059a91e77b84059fbc7ed286ef48c49d",
        "apr06_qualification_risk_2026_11_22": "2019c22506eb320f30977be34b920b1a39e5c1f0",
    }
    for key, expected in merges.items():
        index = current[key]
        child = _load(ROOT / index["checkpoint"])
        assert index["task_id"] == child["task_id"]
        assert index["status"] == child["status"] == "completed"
        assert child["protected_merge_commit"] == expected
        assert child["protected_exact_ci"] == "19_of_19_success"
        assert child["production_deployed"] is False
        assert child["remaining"] == []


def test_residual_external_acceptance_remains_blocked():
    current = _load(CURRENT)
    for key, issue in (
        ("sibur_ppt_current_source_2026_11_22", 686),
        ("apr06_qualification_release_2026_11_22", 406),
        ("dtr679_current_originals_2026_11_22", 679),
        ("pitr_seven_day_2026_11_22", 685),
    ):
        index = current[key]
        child = _load(ROOT / index["checkpoint"])
        assert index["status"] == child["status"] == "blocked"
        assert index["linked_issue"] == issue
        assert child["remaining"]
    assert current["status"] == "in_progress"


def test_product_queue_and_research_only_limits():
    queue = _load(ROOT / ".agent/execution-queue.yaml")["items"]
    assert len(queue) == 66
    assert sum(item["status"] == "done" for item in queue) == 65
    assert [
        (x["task_id"], x["status"], x["authority"])
        for x in queue
        if x["status"] != "done"
    ] == [("COMMERCIAL-WORKFLOW-ARV-069-001", "blocked", "REVIEW")]
    current = _load(CURRENT)
    assert current["sibur_ppt_current_source_2026_11_22"]["production_mutations"] is False
    assert current["apr06_qualification_release_2026_11_22"]["production_deployed"] is False
