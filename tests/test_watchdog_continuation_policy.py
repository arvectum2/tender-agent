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


def test_material_policy_change_renewal_is_attributable_and_reporting_is_visible():
    directive = _yaml(".agent/owner-directive.yaml")
    policy = _yaml(".agent/executor-policy.yaml")
    watchdog = _yaml(".agent/watchdog.yaml")

    assert directive["governance"]["material_executor_policy_change"] is True
    assert (
        directive["governance"]["am4_effect"]
        == "renewed_am4_active_after_attributable_owner_review_2026_09_22"
    )
    assert directive["governance"]["renewal_decision"].endswith(
        "DECISION-2026-09-22-POS-004-ROADMAP-EXECUTOR-AM4-RENEWAL.md"
    )
    company_gate = policy["company_authority_gate"]
    assert company_gate["material_policy_change_recorded_2026_09_18"] is True
    assert company_gate["mandatory_review_deadline"] == "2026-10-22"
    assert company_gate["automatic_merge_after_material_policy_change"] == "ALLOWED_UNDER_RENEWED_AM4"
    assert company_gate["automatic_merge_cycle_state"] == "ACTIVE_RENEWED_2026_09_22"
    assert company_gate["automatic_merges_since_review_including_this_reconciliation_when_merged"] == 7
    assert policy["sources"]["company_authority"]["latest_renewal"].endswith(
        "DECISION-2026-09-22-POS-004-ROADMAP-EXECUTOR-AM4-RENEWAL.md"
    )

    reporting = watchdog["reporting"]
    assert reporting["fail_visible"] is True
    assert reporting["create_placeholder_comment_at_run_start"] is True
    assert reporting["update_same_comment_at_run_end"] is True
    assert reporting["exactly_one_comment_per_invocation"] is True
