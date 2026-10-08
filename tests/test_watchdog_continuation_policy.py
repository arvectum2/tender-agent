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
        == "renewed_am4_active_pr_217_is_6_of_10_if_merged"
    )
    assert directive["governance"]["renewal_decision"].endswith(
        "DECISION-2026-10-08-POS-004-ROADMAP-EXECUTOR-AM4-RENEWAL.md"
    )
    company_gate = policy["company_authority_gate"]
    assert company_gate["material_policy_change_recorded_2026_09_18"] is True
    assert company_gate["mandatory_review_deadline"] == "2026-11-08"
    assert company_gate["automatic_merge_after_material_policy_change"] == "ALLOWED_UNDER_RENEWED_AM4"
    assert company_gate["automatic_merge_cycle_state"] == "ACTIVE_RENEWED_2026_10_08_6_OF_10_IF_PR_217_MERGES"
    assert company_gate["automatic_merges_since_review_including_this_reconciliation_when_merged"] == 6
    assert company_gate["next_automatic_merge"] == "ALLOWED_IF_ALL_AM4_GATES_PASS"
    assert policy["sources"]["company_authority"]["latest_renewal"].endswith(
        "DECISION-2026-10-08-POS-004-ROADMAP-EXECUTOR-AM4-RENEWAL.md"
    )

    reporting = watchdog["reporting"]
    assert reporting["fail_visible"] is True
    assert reporting["create_placeholder_comment_at_run_start"] is True
    assert reporting["update_same_comment_at_run_end"] is True
    assert reporting["exactly_one_comment_per_invocation"] is True


def test_full_commercial_workflow_history_is_preserved_but_forecast_is_deferred():
    directive = _yaml(".agent/owner-directive.yaml")
    roadmap = _yaml("docs/roadmap/master-roadmap.yaml")
    queue = _yaml(".agent/execution-queue.yaml")

    expected_scope = [
        "ARV-015",
        "ARV-019",
        "ARV-022",
        "ARV-053",
        "ARV-055",
        "ARV-057",
        "ARV-059",
        "ARV-060",
        "ARV-063",
        "ARV-064",
        "ARV-066",
        "ARV-069",
    ]
    admission = directive["commercial_workflow_admission_2026_10_07"]
    assert admission["historical_items"] == expected_scope

    branch = next(
        item
        for item in roadmap["continuation_branches"]["branches"]
        if item["branch_id"] == "COMMERCIAL-WORKFLOW"
    )
    assert branch["historical_items"] == expected_scope

    queue_items = {item["task_id"]: item for item in queue["items"]}
    for task_id in [
        "ARV-015-OPERATOR-PROFILE-PARSER-001",
        "COMMERCIAL-WORKFLOW-ARV-019-001",
        "COMMERCIAL-WORKFLOW-ARV-022-001",
        "COMMERCIAL-WORKFLOW-ARV-053-001",
        "COMMERCIAL-WORKFLOW-ARV-055-001",
        "COMMERCIAL-WORKFLOW-ARV-057-001",
        "COMMERCIAL-WORKFLOW-ARV-059-001",
        "COMMERCIAL-WORKFLOW-ARV-060-001",
        "COMMERCIAL-WORKFLOW-ARV-063-001",
        "COMMERCIAL-WORKFLOW-ARV-064-001",
        "COMMERCIAL-WORKFLOW-ARV-066-001",
    ]:
        assert queue_items[task_id]["status"] == "done"

    forecast = queue_items["COMMERCIAL-WORKFLOW-ARV-069-001"]
    assert forecast["status"] == "blocked"
    assert forecast["authority"] == "REVIEW"
    assert forecast["auto_merge"] is False


def test_commercial_workflow_essential_v1_is_closed_and_active_roadmap_moves_to_arv061():
    roadmap = _yaml("docs/roadmap/master-roadmap.yaml")
    queue = _yaml(".agent/execution-queue.yaml")

    progress = roadmap["current_status_summary"]["commercial_workflow"]
    assert progress["essential_v1_completed"] == 11
    assert progress["historical_total"] == 12
    assert progress["completed_items"][-1] == "ARV-066"
    assert progress["deferred_experiment"] == "ARV-069"
    assert progress["state"] == "essential_v1_complete_forecast_deferred"

    active = roadmap["current_status_summary"]["active_product_roadmap"]
    assert active["next_outcome"] == "APR-01-FAST-CITED-PREANALYSIS"
    assert active["next_queue_item"] == "ACTIVE-ROADMAP-ARV-061-001"

    items = {item["task_id"]: item for item in queue["items"]}
    assert items["COMMERCIAL-WORKFLOW-ARV-066-001"]["status"] == "done"
    assert items["ACTIVE-ROADMAP-ARV-061-001"]["status"] == "ready"


def test_owner_optimized_active_product_roadmap_controls_continuation():
    roadmap = _yaml("docs/roadmap/master-roadmap.yaml")
    directive = _yaml(".agent/owner-directive.yaml")
    queue = _yaml(".agent/execution-queue.yaml")

    active = roadmap["active_product_roadmap_2026_10_08"]
    assert len(active["outcomes"]) <= 15
    assert [item["id"] for item in active["outcomes"][:3]] == [
        "APR-01-FAST-CITED-PREANALYSIS",
        "APR-02-223FZ-BREADTH",
        "APR-03-PRODUCTION-RUNTIME",
    ]
    assert directive["active_product_roadmap_optimization_2026_10_08"]["status"] == "active"

    queue_items = {item["task_id"]: item for item in queue["items"]}
    assert queue_items["ACTIVE-ROADMAP-ARV-061-001"]["status"] == "ready"
    assert queue_items["ACTIVE-ROADMAP-ARV-061-001"]["authority"] == "AUTO"
    assert queue_items["COMMERCIAL-WORKFLOW-ARV-069-001"]["status"] == "blocked"
    assert queue_items["COMMERCIAL-WORKFLOW-ARV-069-001"]["authority"] == "REVIEW"
    assert queue_items["COMMERCIAL-WORKFLOW-ARV-069-001"]["auto_merge"] is False


def test_trigger_backlog_keeps_technology_choices_out_of_active_commitments():
    roadmap = _yaml("docs/roadmap/master-roadmap.yaml")
    trigger_items = roadmap["trigger_backlog_2026_10_08"]["items"]
    mapped = {legacy for item in trigger_items for legacy in item["legacy_mapping"]}

    for legacy_id in ["ARV-028", "ARV-029", "ARV-047", "ARV-048", "ARV-049", "ARV-062", "ARV-075", "ARV-046", "ARV-045", "ARV-070", "ARV-069"]:
        assert legacy_id in mapped

    active_mapped = {
        legacy
        for outcome in roadmap["active_product_roadmap_2026_10_08"]["outcomes"]
        for legacy in outcome.get("legacy_mapping", [])
    }
    assert "ARV-047" not in active_mapped
    assert "ARV-048" not in active_mapped
    assert "ARV-049" not in active_mapped
    assert "ARV-069" not in active_mapped
