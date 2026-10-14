"""Only synthetic signed reviewer fixtures pass external-source-gold intake."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.acceptance.freeze_r4_independent_human_gold import (
    accept_independent_submission,
)
from src.modules.benchmark_pipeline.contract import canonical_sha256, write_artifact
from tests.test_r4_external_gold_intake import (
    P3,
    synthetic_signed_review,
)


def signed_synthetic_fixture(tmp_path: Path):
    args = synthetic_signed_review(tmp_path)
    bundle_dir = tmp_path / "pack"
    bundle_dir.mkdir()
    write_artifact(bundle_dir / "case_manifest.json", args["source_manifest"], "case_manifest")
    write_artifact(bundle_dir / "evaluator_bundle.json", args["evaluator_bundle"], "evaluator_bundle")
    submission = {
        "draft_status": "EXPERT_SUBMITTED",
        "sut_inference_allowed": False,
        "case_id": args["evaluator_bundle"]["case_id"],
        "source_bundle_sha256": args["evaluator_bundle"]["source_bundle_sha256"],
        "blind_discovery_label": args["discovery_label"],
        "blind_document_truth": args["document_truth"],
        "external_human_reviewer_attestation": args["signed_attestation"],
    }
    heldout_case = {
        "registry_number": args["evaluator_bundle"]["procurement"]["notice_number"],
        "official_zip_sha256": "a" * 64,
        "official_xml_sha256": "b" * 64,
        "original_attachment_sha256": [d["sha256"] for d in args["evaluator_bundle"]["documents"]],
        "source_attestation": "OFFICIAL_EIS_FIRST_PARTY_SHA_VERIFIED",
        "blind_legal_gold": "NOT_PREPARED",
        "sut_exposure": "FORBIDDEN_UNTIL_GOLD_FREEZE",
    }
    lock = {
        "source_set_id": "test_real_source_lock",
        "locked_at_utc": args["evaluator_bundle"]["prepared_at"],
        "selection": "SYNTHETIC_TEST_CASE_NOT_REAL_HOLDOUT",
        "case_count": 1,
        "cases": [heldout_case],
        "case_evidence_sha256": canonical_sha256([heldout_case]),
        "gold_freeze_status": "PENDING_INDEPENDENT_EXPERT",
        "sut_run_authorized": False,
        "semantic_precision": None,
        "semantic_recall": None,
        "bid_ready": False,
    }
    lock["immutable_lock_sha256"] = canonical_sha256(lock)
    return {
        "bundle_dir": bundle_dir,
        "original_source_root": tmp_path,
        "submission": submission,
        "trusted_reviewer_roster": args["trusted_reviewer_keys"],
        "immutable_holdout_lock": lock,
        "frozen_at": P3,
    }


def test_external_signed_labels_produce_canonical_frozen_receipt_synthetic_only(tmp_path):
    args = signed_synthetic_fixture(tmp_path)
    result = accept_independent_submission(**args)
    assert result["frozen"]["case_id"].startswith("SYNTHETIC")
    assert len(result["frozen"]["label_set_sha256"]) == 64
    assert not list(tmp_path.glob("**/frozen_label.json"))


def test_refuse_blank_or_sut_exposed_or_changed_source(tmp_path):
    args = signed_synthetic_fixture(tmp_path)
    args["submission"]["draft_status"] = "TEMPLATE_ONLY_NOT_HUMAN_GOLD"
    with pytest.raises(ValueError, match="Blank"):
        accept_independent_submission(**args)

    args["submission"]["draft_status"] = "EXPERT_SUBMITTED"
    args["submission"]["sut_inference_allowed"] = True
    with pytest.raises(ValueError, match="SUT exposure"):
        accept_independent_submission(**args)

    args["submission"]["sut_inference_allowed"] = False
    args["submission"]["source_bundle_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="different"):
        accept_independent_submission(**args)


def test_without_owner_trusted_public_key_no_freeze_possible(tmp_path):
    args = signed_synthetic_fixture(tmp_path)
    args["trusted_reviewer_roster"] = {}
    with pytest.raises(ValueError, match="not enrolled"):
        accept_independent_submission(**args)



def test_substituted_holdout_cohort_cannot_freeze_gold(tmp_path):
    args = signed_synthetic_fixture(tmp_path)
    args["immutable_holdout_lock"]["cases"][0]["original_attachment_sha256"] = ["c" * 64]
    with pytest.raises(ValueError):
        accept_independent_submission(**args)
