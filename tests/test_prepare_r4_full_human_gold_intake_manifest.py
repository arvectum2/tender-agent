"""Only source identity/receipts are checked; never synthesizes expert labels."""
from __future__ import annotations

import copy
import os
from pathlib import Path

import pytest

from scripts.acceptance.freeze_r4_independent_human_cohort import (
    validate_full_cohort_enrollment,
)
from scripts.acceptance.prepare_r4_full_human_gold_intake_manifest import (
    build_empty_cohort_intake_manifest,
)


def private_blind15_inputs():
    root = os.environ.get("TA_PRIVATE_R4_SOURCE_ROOT")
    if not root:
        pytest.skip("Real private EIS source-only receipts only exist on authorized Mac")
    base = Path(root)
    pilot = base / "ai-expert-20261014/semantic-holdout-prospective"
    stage2 = base / "ai-expert-20261015/stage2-real-source-cohort-20261015"
    stage3 = base / "ai-expert-20261015/stage3-cross-vendor-original-capture"
    stage4 = base / "ai-expert-20261015/stage4-prospective-pages23"
    sources = [
        pilot / "holdout-lock-private.json",
        stage2 / "stage2-partial4-blind-lock-private.json",
        stage3 / "stage3-four-source-only-blind-lock-private.json",
        stage4 / "stage4-firstfour-source-only-blind-lock-private.json",
    ]
    if any(not p.is_file() for p in sources):
        pytest.skip("Private cohort files are unavailable")
    import json

    public = json.loads(Path(
        "docs/acceptance/data/TA_R4_FINAL_15_SOURCE_ONLY_BLIND_COHORTS_2026-10-15.json"
    ).read_text())
    return {
        "public_immutable_summary": public,
        "source_lock_paths": sources,
        "evaluator_roots": [
            pilot / "blind-evaluator-packs",
            stage2 / "stage2-partial4-blind-evaluator-packs",
            stage3 / "stage3-four-blind-evaluator-packs",
            stage4 / "stage4-firstfour-blind-evaluator-packs",
        ],
        "original_source_roots": [
            pilot,
            stage2 / "official-eis-originals",
            stage3 / "official-eis-stage3-eight",
            stage4 / "official-eis-first-twelve",
        ],
    }


def test_real_eis_source_only_fifteen_case_roster_no_signed_labels():
    inputs = private_blind15_inputs()
    report = build_empty_cohort_intake_manifest(**inputs)
    assert report["case_count"] == len(report["cases"]) == 15
    assert report["signed_case_count"] == 0
    assert report["sut_run_authorized"] is False
    assert report["bid_ready"] is False
    assert report["trusted_public_reviewer_keys_supplied"] is False
    assert all(row["signed_submission_path"] is None for row in report["cases"])
    assert all(row["case_id"].startswith("R4-BLIND-") for row in report["cases"])
    assert len({row["case_id"] for row in report["cases"]}) == 15
    from json import loads

    locks = [loads(p.read_text()) for p in inputs["source_lock_paths"]]
    with pytest.raises(ValueError, match="All signed cases"):
        validate_full_cohort_enrollment(
            immutable_locks=locks,
            published_summary=inputs["public_immutable_summary"],
            case_inputs=[],  # absolutely no gold on any real source
        )


def test_real_incomplete_group_fails_without_writing_gold():
    inputs = private_blind15_inputs()
    inputs["evaluator_roots"] = inputs["evaluator_roots"][:-1]
    with pytest.raises(ValueError, match="Each blind group"):
        build_empty_cohort_intake_manifest(**inputs)


def test_real_published_sha_tamper_rejected_without_gold():
    inputs = private_blind15_inputs()
    inputs["public_immutable_summary"] = copy.deepcopy(inputs["public_immutable_summary"])
    inputs["public_immutable_summary"]["blind_lock_sha256"][0] = "0" * 64
    with pytest.raises(ValueError, match="published SHA"):
        build_empty_cohort_intake_manifest(**inputs)


def test_real_original_document_root_substitution_rejected(tmp_path: Path):
    inputs = private_blind15_inputs()
    inputs["original_source_roots"][0] = tmp_path
    with pytest.raises((ValueError, FileNotFoundError), match="source|not found|Missing|missing"):
        build_empty_cohort_intake_manifest(**inputs)
