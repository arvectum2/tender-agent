"""Stage4 final source-only lock: real receipts only with private fixture opt-in."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from scripts.acceptance.finalize_r4_stage4_source_lock import (
    finalize_stage4_source_only,
)
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    verify_cohort_lock,
)


def _real():
    env=os.environ.get("TA_PRIVATE_R4_SOURCE_ROOT")
    if not env:
        pytest.skip("Mac first-party original source evidence not mounted")
    root=Path(env)
    capture=root/"ai-expert-20261015/stage4-prospective-pages23"
    if not (capture/"stage4-firstfour-source-only-blind-lock-private.json").is_file():
        pytest.skip("Original source-only blind lock unavailable")
    read=lambda p:json.loads(Path(p).read_text())
    intent=read("docs/acceptance/data/TA_R4_STAGE4_PROSPECTIVE_PAGES23_INTENT_2026-10-15.json")
    prior=[read(p) for p in (
        root/"ai-expert-20261014/semantic-holdout-prospective/holdout-lock-private.json",
        root/"ai-expert-20261015/stage2-real-source-cohort-20261015/stage2-partial4-blind-lock-private.json",
        root/"ai-expert-20261015/stage3-cross-vendor-original-capture/stage3-four-source-only-blind-lock-private.json",
    )]
    previous=read(capture/"stage4-firstfour-source-only-blind-lock-private.json")
    arguments={
        "intent":intent,
        "capture":read(capture/"private-source-capture-receipt.json"),
        "actual_discovery":read(capture/"stage4-source-ranked-first-twelve-private.json"),
        "original_html_root":capture,
        "official_archive_root":capture/"official-eis-first-twelve",
        "actual_official_cases":read(
            capture/"official-eis-first-twelve/source-only-attestation-checkpoint-private.json"
        )["cases"],
        "development_audit":read(
            "docs/acceptance/data/TDP_R4_20_TRUE_COMPETITIVE_ORIGINAL_SEMANTIC_AUDIT_2026-10-14.json"
        ),
        "three_previous_locks":prior,
        "freeze_at_utc":previous["locked_at_utc"],
    }
    return arguments,previous,capture


def test_real_stage4_lock_is_replayable_with_exact_first_four_source_ids():
    args,previous,_=_real()
    lock,receipt=finalize_stage4_source_only(**args)
    assert lock==previous
    verify_cohort_lock(lock)
    assert receipt["all_twelve_source_candidates_attempted"] is True
    assert receipt["official_source_complete_count"]==9
    assert receipt["source_independent_count_before_target_cap"]==6
    assert receipt["source_locked_count"]==4
    assert receipt["independent_but_not_in_frozen_target_count"]==2
    assert receipt["raw_sha_verified_locked_original_count"]==17
    assert len(receipt["excluded_source_positions"])==6
    assert receipt["gold_signed_count"]==0 and receipt["sut_ran"] is False


def test_stage4_missing_prior_lock_is_hard_failure():
    args,_,_=_real()
    args["three_previous_locks"]=args["three_previous_locks"][:2]
    with pytest.raises(ValueError,match="three previous"):
        finalize_stage4_source_only(**args)


def test_stage4_official_source_order_cannot_change():
    args,_,_=_real()
    original=copy.deepcopy(args["actual_official_cases"])
    args["actual_official_cases"]=list(reversed(args["actual_official_cases"]))
    with pytest.raises(ValueError,match="Order or membership"):
        finalize_stage4_source_only(**args)
    assert args["actual_official_cases"]!=original


def test_stage4_tampered_discovery_receipt_is_rejected():
    args,_,_=_real()
    args["actual_discovery"]=copy.deepcopy(args["actual_discovery"])
    args["actual_discovery"]["selected_discovery_only"][0]["registry_number"]="9999999999999999999"
    with pytest.raises(ValueError,match="source order changed"):
        finalize_stage4_source_only(**args)


def test_stage4_additional_source_cap_cannot_expand_automatically():
    args,_,_=_real()
    args["intent"]=copy.deepcopy(args["intent"])
    args["intent"]["target_new_verified_cases"]=6
    with pytest.raises(ValueError,match="intent changed|immutable source intent"):
        finalize_stage4_source_only(**args)
