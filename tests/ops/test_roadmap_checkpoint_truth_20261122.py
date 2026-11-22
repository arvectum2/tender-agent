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



def test_admitted_inventory_queue_is_completed_without_review_override():
    queue = yaml.safe_load(QUEUE.read_text(encoding="utf8"))
    assert sum(x["status"] == "done" for x in queue["items"]) == 65
    open_items = [x for x in queue["items"] if x["status"] != "done"]
    assert [(x["task_id"], x["status"], x["authority"]) for x in open_items] == [
        ("COMMERCIAL-WORKFLOW-ARV-069-001", "blocked", "REVIEW")
    ]
    by_id = {x["task_id"]: x for x in queue["items"]}
    names = ["TA-SIBUR-SOURCE-DISCOVERY-001", "TA-GEH-SOURCE-DISCOVERY-001",
             "TA-AI-TRADING-SOURCE-DISCOVERY-001"]
    assert [by_id[n]["order"] for n in names] == [1130, 1140, 1150]
    assert all(by_id[n]["authority"] == "AUTO" and by_id[n]["status"] == "done" for n in names)


def test_child_completion_requires_independently_verified_protected_merge():
    parent = yaml.safe_load(CURRENT.read_text(encoding="utf8"))
    required = {
        "roadmap_reconciliation_2026_11_22": "5f0986f456f040032c26ba9cec50f65718c216ac",
        "sibur_source_discovery_2026_11_22": "879dcbc3321f3497e6131c99d5df040f6e7ac3ef",
        "geh_source_discovery_2026_11_22": "3c1e0eb1a7ee8071b9d494f8e5b84580d0c53dc4",
        "ai_trading_source_discovery_2026_11_22": "4f13b1239b7951333236d03f2c30f63c27252795",
    }
    for key, merge in required.items():
        index = parent[key]
        child = yaml.safe_load((ROOT / index["checkpoint"]).read_text(encoding="utf8"))
        assert index["task_id"] == child["task_id"]
        assert index["status"] == child["status"] == "completed"
        assert child["protected_merge_commit"] == merge
        assert child["protected_exact_ci"] == "19_of_19_success"
        assert child["production_deployed"] is False
        assert child["remaining"] == []
    assert parent["status"] == "in_progress"


def test_inventory_results_do_not_claim_new_live_market_access():
    import json

    docs = ROOT / "docs/roadmap"
    sibur = json.loads((docs / "ta_sibur_source_reuse_inventory_20261122.json").read_text())
    geh = json.loads((docs / "ta_geh_source_reuse_inventory_20261122.json").read_text())
    paper = json.loads((docs / "ta_ai_trading_source_reuse_inventory_20261122.json").read_text())
    assert sibur["authorized_srm_session"] is False
    assert geh["live_platform_api_verified"] is False
    assert paper["mode"] == "PAPER_SIMULATION_ONLY"
    assert paper["real_bid_allowed"] is paper["real_order_allowed"] is False
    assert paper["sample_proof"]["simulated_bids_run"] == 0
