"""APR-06 commercial acceptance must never fabricate a completed benchmark."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.modules.commercial_acceptance.acceptance import (
    AcceptanceError,
    _new_file,
    freeze_manifest,
    main,
    score,
    thresholds_valid,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "docs/acceptance/apr06_candidate_pool_2026-10-09.json"
THRESHOLDS = ROOT / "docs/acceptance/apr06_thresholds_proposed.json"


def candidate_pool() -> dict:
    return json.loads(POOL.read_text(encoding="utf-8"))


def policy() -> dict:
    return json.loads(THRESHOLDS.read_text(encoding="utf-8"))


def verified_corpus() -> dict:
    manifest = candidate_pool()
    for idx, c in enumerate(manifest["cases"]):
        c["verification"] = {
            "state": "eis_verified",
            "eis_source_url": "https://zakupki.gov.ru/epz/order/extendedsearch/results.html",
            "notice_sha256": f"{idx + 1:064x}",
            "document_sha256": [f"{idx + 100:064x}"],
            "verified_at": "2026-10-09T09:00:00+03:00",
        }
    return manifest


def frozen_corpus() -> dict:
    return freeze_manifest(verified_corpus(), frozen_at="2026-10-09T10:00:00+03:00")


def observation(case: dict) -> dict:
    return {
        "schema_version": "apr06-observation-v1",
        "reg_number": case["reg_number"], "law": case["law"],
        "source_manifest_sha256": case["verification"]["notice_sha256"],
        "workflow_status": "completed_with_human_review",
        "run_id": "test-run-" + case["reg_number"],
        "started_at": "2026-10-09T10:00:00+03:00",
        "operator_review": {
            "reviewer_id": "synthetic-test-reviewer",
            "evidence_ref": "test-only:human-review-" + case["reg_number"],
            "decision": "NO_GO",
            "decided_at": "2026-10-09T10:20:00+03:00",
        },
        "suggested_decision": "NO_GO",
        "analysis_evidence_ref": "test-only:analysis-" + case["reg_number"],
        "claims": [{"claim_id": "claim-1", "citation_verified": True, "source_ref": "test-only:doc"}],
        "reviewed_fields": 10, "corrected_fields": 0,
        "required_facts": 5, "unsupported_facts": 0,
        "human_confirmed_blockers": [], "reported_blockers": [],
        "application_package": {"reviewed": True, "required_rework": False},
        "confirmed_defects": [],
    }


def observations(manifest: dict) -> dict[str, dict]:
    return {x["reg_number"]: observation(x) for x in manifest["cases"]}


def approved(policy_data: dict) -> dict:
    policy_data = copy.deepcopy(policy_data)
    policy_data["approval"] = {
        "state": "approved", "approver": "SYNTHETIC UNIT TEST ONLY",
        "approved_at": "2026-10-09T11:00:00+03:00",
        "decision_reference": "test-only:owner-signoff",
    }
    return policy_data


def test_candidates_are_real_registry_shaped_diverse_but_not_frozen():
    manifest = candidate_pool()
    assert validate_manifest(manifest) == {
        "count": 28, "laws": {"44fz": 20, "223fz": 8}, "verified": 0,
    }
    assert "freeze" not in manifest
    with pytest.raises(AcceptanceError, match="not verified"):
        freeze_manifest(manifest, frozen_at="2026-10-09T09:00:00+03:00")
    with pytest.raises(AcceptanceError, match="not verified"):
        validate_manifest(manifest, require_frozen=True)


def test_verified_manifest_is_digest_locked_after_freeze():
    manifest = frozen_corpus()
    assert validate_manifest(manifest, require_frozen=True)["verified"] == 28
    tampered = copy.deepcopy(manifest)
    tampered["cases"][0]["subject"] = "silently altered after freeze"
    with pytest.raises(AcceptanceError, match="digest"):
        validate_manifest(tampered, require_frozen=True)
    with pytest.raises(AcceptanceError, match="re-freeze"):
        freeze_manifest(manifest, frozen_at="2026-10-09T12:00:00+03:00")


def test_duplicate_or_wrong_law_fails():
    manifest = candidate_pool()
    manifest["cases"][0]["reg_number"] = manifest["cases"][1]["reg_number"]
    with pytest.raises(AcceptanceError, match="duplicate"):
        validate_manifest(manifest)
    manifest = candidate_pool()
    manifest["cases"][0]["law"] = "223fz"
    with pytest.raises(AcceptanceError, match="invalid EIS"):
        validate_manifest(manifest)


def test_corpus_needs_real_provenance_and_hashes():
    manifest = candidate_pool()
    manifest["cases"][0]["listing_source_url"] = "http://unsafe.example/tender"
    with pytest.raises(AcceptanceError, match="HTTPS"):
        validate_manifest(manifest)
    manifest = verified_corpus()
    manifest["cases"][0]["verification"]["document_sha256"] = []
    with pytest.raises(AcceptanceError, match="hashed documents"):
        validate_manifest(manifest)
    manifest = verified_corpus()
    manifest["cases"][0]["verification"]["eis_source_url"] = "https://zakupki.kontur.ru/"
    with pytest.raises(AcceptanceError, match="official EIS"):
        validate_manifest(manifest)


def test_policy_requires_all_seven_metrics_and_explicit_real_approval():
    p = policy()
    assert set(thresholds_valid(p)) == {
        "time_to_decision_minutes_p90", "manual_correction_rate",
        "citation_coverage", "unknown_rate", "missed_blockers",
        "false_go_no_go", "application_package_rework",
    }
    p["approval"]["state"] = "approved"
    with pytest.raises(AcceptanceError, match="approver"):
        thresholds_valid(p)
    p = policy()
    p["limits"]["citation_coverage"] = 1.01
    with pytest.raises(AcceptanceError, match="Rates"):
        thresholds_valid(p)


def test_complete_synthetic_unit_test_is_always_pending_owner_if_proposed():
    manifest = frozen_corpus()
    out = score(manifest, observations(manifest), policy())
    assert out["status"] == "PENDING_OWNER_THRESHOLD_APPROVAL"
    assert out["eligible_count"] == out["corpus_size"] == 28
    assert out["operator_verified_cases"] == 28
    assert out["metrics"]["citation_coverage"] == 1.0
    assert out["metrics"]["time_to_decision_minutes_p90"] == 20
    assert out["regressions_total"] == 0


def test_unit_test_only_approved_policy_all_metrics_pass():
    manifest = frozen_corpus()
    out = score(manifest, observations(manifest), approved(policy()))
    assert out["status"] == "ACCEPTED"
    assert all(out["threshold_checks"].values())
    assert out["no_automatic_bid_or_payment"] is True


def test_missing_observation_must_not_be_counted_as_success():
    manifest = frozen_corpus()
    obs = observations(manifest)
    del obs[manifest["cases"][0]["reg_number"]]
    out = score(manifest, obs, approved(policy()))
    assert out["status"] == "INSUFFICIENT_REVIEW_EVIDENCE"
    assert out["eligible_count"] == 27
    assert len(out["unreviewed_or_invalid"]) == 1


def test_fake_review_ambiguous_time_or_missing_citation_fails_closed():
    manifest = frozen_corpus()
    obs = observations(manifest)
    reg = manifest["cases"][0]["reg_number"]
    obs[reg]["operator_review"]["reviewer_id"] = ""
    assert score(manifest, obs, approved(policy()))["status"] == "INSUFFICIENT_REVIEW_EVIDENCE"
    obs[reg] = observation(manifest["cases"][0])
    obs[reg]["operator_review"]["decided_at"] = obs[reg]["started_at"]
    assert score(manifest, obs, approved(policy()))["eligible_count"] == 27
    obs[reg] = observation(manifest["cases"][0])
    obs[reg]["claims"] = []
    assert score(manifest, obs, approved(policy()))["eligible_count"] == 27


def test_human_confirmed_missed_blocker_requires_a_regression_record():
    manifest = frozen_corpus()
    reg = manifest["cases"][0]["reg_number"]
    obs = observations(manifest)
    obs[reg]["human_confirmed_blockers"] = ["fatal_license"]
    missing = score(manifest, obs, approved(policy()))
    assert missing["status"] == "INSUFFICIENT_REVIEW_EVIDENCE"
    obs[reg]["confirmed_defects"] = [{
        "defect_id": "missed_blocker:fatal_license",
        "source_ref": "test-only:confirmed-requirement",
        "summary": "Test-only missed license blocker",
    }]
    failed = score(manifest, obs, approved(policy()))
    assert failed["status"] == "FAILED_ACCEPTANCE"
    assert failed["metrics"]["missed_blockers"] == 1
    assert failed["regressions_total"] == 1


def test_cross_corpus_run_id_and_source_snapshot_mismatch_fail_closed():
    manifest = frozen_corpus()
    obs = observations(manifest)
    a, b = manifest["cases"][:2]
    obs[a["reg_number"]]["source_manifest_sha256"] = b["verification"]["notice_sha256"]
    assert score(manifest, obs, approved(policy()))["eligible_count"] == 27
    obs[a["reg_number"]] = observation(a)
    obs[b["reg_number"]]["run_id"] = obs[a["reg_number"]]["run_id"]
    result = score(manifest, obs, approved(policy()))
    assert result["status"] == "INSUFFICIENT_REVIEW_EVIDENCE"
    assert result["eligible_count"] == 27


def test_unknown_metrics_do_not_pass_when_no_packages_reviewed():
    manifest = frozen_corpus()
    obs = observations(manifest)
    for x in obs.values():
        x["application_package"] = {"reviewed": False, "required_rework": False}
    report = score(manifest, obs, approved(policy()))
    assert report["metrics"]["application_package_rework"] is None
    assert report["status"] == "INSUFFICIENT_REVIEW_EVIDENCE"


def test_no_overwrite_acceptance_artifacts(tmp_path: Path):
    target = tmp_path / "frozen.json"
    _new_file(target, {"first": True})
    original = target.read_bytes()
    with pytest.raises(AcceptanceError, match="already exists"):
        _new_file(target, {"first": False})
    assert target.read_bytes() == original


def test_candidate_cli_validate_not_freeze(tmp_path: Path, capsys):
    assert main(["validate", "--manifest", str(POOL)]) == 0
    output = tmp_path / "freeze.json"
    assert main(["freeze", "--manifest", str(POOL), "--output", str(output),
                 "--frozen-at", "2026-10-09T11:00:00+03:00"]) == 2
    assert not output.exists()
    result = capsys.readouterr().out
    assert "not verified" in result


def test_manifest_missing_case_fails_20_threshold():
    manifest = candidate_pool()
    manifest["cases"] = manifest["cases"][:19]
    with pytest.raises(AcceptanceError, match="20-30"):
        validate_manifest(manifest)

def test_false_go_no_go_and_corrections_must_be_regressions():
    manifest = frozen_corpus()
    obs = observations(manifest)
    reg = manifest["cases"][0]["reg_number"]
    obs[reg]["suggested_decision"] = "GO"
    obs[reg]["operator_review"]["decision"] = "NO_GO"
    assert score(manifest, obs, approved(policy()))["status"] == "INSUFFICIENT_REVIEW_EVIDENCE"
    obs[reg]["confirmed_defects"] = [{
        "defect_id": "false_decision",
        "source_ref": "test-only:counterevidence",
        "summary": "Dangerous false-positive GO",
    }]
    report = score(manifest, obs, approved(policy()))
    assert report["status"] == "FAILED_ACCEPTANCE"
    assert report["metrics"]["false_go_no_go"] > 0
    obs[reg]["suggested_decision"] = "NO_GO"
    obs[reg]["operator_review"]["decision"] = "NO_GO"
    obs[reg]["corrected_fields"] = 1
    obs[reg]["confirmed_defects"] = []
    assert score(manifest, obs, approved(policy()))["status"] == "INSUFFICIENT_REVIEW_EVIDENCE"
