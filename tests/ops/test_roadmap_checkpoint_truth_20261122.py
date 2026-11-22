"""Fail-closed checks on canonical roadmap and active execution checkpoints."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / ".agent/current-task.yaml"
QUEUE = ROOT / ".agent/execution-queue.yaml"


def test_parent_checkpoint_has_unique_yaml_keys():
    document = yaml.compose(CURRENT.read_text(encoding="utf8"))

    def visit(node, parent="root"):
        if isinstance(node, yaml.MappingNode):
            keys = set()
            for key, value in node.value:
                label = key.value
                assert label not in keys, f"duplicate YAML key: {parent}/{label}"
                keys.add(label)
                visit(value, parent + "/" + label)
        elif isinstance(node, yaml.SequenceNode):
            for value in node.value:
                visit(value, parent)

    visit(document)


def test_completed_child_checkpoints_not_duplicated():
    parent = yaml.safe_load(CURRENT.read_text(encoding="utf8"))
    for key in ("wsf07b_exact_bearer_20261117",
                "pitr127_restore_readonly_audit_2026_11_22",
                "pitr_exact_wal_2026_11_22"):
        child = parent[key]
        proof = yaml.safe_load((ROOT / child["checkpoint"]).read_text(encoding="utf8"))
        assert child["status"] == proof["status"] == "completed"
    assert parent["pitr_exact_wal_2026_11_22"]["isolated_restore_executed"] is True


def test_independent_unmet_gates_are_blocked():
    parent = yaml.safe_load(CURRENT.read_text(encoding="utf8"))
    for key, issue in (("dtr679_current_originals_2026_11_22", 679),
                       ("pitr_seven_day_2026_11_22", 685)):
        index = parent[key]
        proof = yaml.safe_load((ROOT / index["checkpoint"]).read_text(encoding="utf8"))
        assert index["status"] == proof["status"] == "blocked"
        assert index["linked_issue"] == issue
        assert proof["remaining"]


def test_ready_queue_order_and_review_gate_unchanged():
    queue = yaml.safe_load(QUEUE.read_text(encoding="utf8"))
    open_items = [item for item in queue["items"] if item["status"] != "done"]
    assert [(item["task_id"], item["status"]) for item in open_items] == [
        ("COMMERCIAL-WORKFLOW-ARV-069-001", "blocked"),
        ("TA-SIBUR-SOURCE-DISCOVERY-001", "ready"),
        ("TA-GEH-SOURCE-DISCOVERY-001", "ready"),
        ("TA-AI-TRADING-SOURCE-DISCOVERY-001", "ready"),
    ]
    assert open_items[0]["authority"] == "REVIEW"
    assert all(item["authority"] == "AUTO" for item in open_items[1:])
