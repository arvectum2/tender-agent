from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _yaml(path: str):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def test_owner_directive_materializes_only_one_deterministic_bounded_item():
    directive = _yaml(".agent/owner-directive.yaml")
    roadmap = _yaml("docs/roadmap/master-roadmap.yaml")
    queue = _yaml(".agent/execution-queue.yaml")

    assert directive["status"] == "active"
    continuation = directive["continuation"]
    assert continuation["enabled"] is True
    assert continuation["branch_order"] == "document_order"
    assert continuation["item_order"] == "historical_items_order"
    assert continuation["max_new_admissions_per_run"] == 1
    assert continuation["bounded_materialization"]["fallback_mode"] == "REVALIDATION"
    assert continuation["bounded_materialization"]["implementation_invention_allowed"] is False

    first_branch = roadmap["continuation_branches"]["branches"][0]
    assert first_branch["branch_id"] == "CORE-QUALITY-PILOT"
    assert first_branch["historical_items"][0] == "ARV-002"

    items = {item["task_id"]: item for item in queue["items"]}
    next_item = items["ARV-002-REVALIDATION-001"]
    assert next_item["roadmap_scope"] == ["ARV-002"]
    assert next_item["continuation_mode"] == "REVALIDATION"
    assert next_item["authority"] == "AUTO"


def test_material_policy_change_fails_automatic_merge_closed_and_reporting_is_visible():
    directive = _yaml(".agent/owner-directive.yaml")
    policy = _yaml(".agent/executor-policy.yaml")
    watchdog = _yaml(".agent/watchdog.yaml")

    assert directive["governance"]["material_executor_policy_change"] is True
    assert (
        directive["governance"]["am4_effect"]
        == "future_automatic_merges_fail_closed_to_review_until_attributable_owner_renewal"
    )
    company_gate = policy["company_authority_gate"]
    assert company_gate["material_policy_change_recorded_2026_09_18"] is True
    assert company_gate["automatic_merge_after_material_policy_change"] == "REVIEW_UNTIL_OWNER_RENEWAL"

    reporting = watchdog["reporting"]
    assert reporting["fail_visible"] is True
    assert reporting["create_placeholder_comment_at_run_start"] is True
    assert reporting["update_same_comment_at_run_end"] is True
    assert reporting["exactly_one_comment_per_invocation"] is True
