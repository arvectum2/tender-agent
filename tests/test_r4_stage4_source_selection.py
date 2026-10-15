"""Reproduce immutable stage4 first-twelve IDs without any model or legal labels."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo.r4_stage4_source_selection import (
    select_stage4_first_twelve,
)


def prior_source_only() -> tuple[dict, Path]:
    path=os.environ.get("TA_PRIVATE_R4_SOURCE_ROOT")
    if not path:
        pytest.skip("Original SHA-pinned EIS evidence only on authorized SSD")
    root=Path(path)
    latest=root/"ai-expert-20261015/stage4-prospective-pages23"
    if not (latest/"stage4-source-ranked-first-twelve-private.json").is_file():
        pytest.skip("Stage4 pre-registered source fixture unavailable")
    read=lambda p:json.loads(p.read_text())
    kwargs={
        "intent":read(Path("docs/acceptance/data/TA_R4_STAGE4_PROSPECTIVE_PAGES23_INTENT_2026-10-15.json")),
        "capture_receipt":read(latest/"private-source-capture-receipt.json"),
        "original_source_root":latest,
        "development_audit":read(Path("docs/acceptance/data/TDP_R4_20_TRUE_COMPETITIVE_ORIGINAL_SEMANTIC_AUDIT_2026-10-14.json")),
        "previous_locks":[read(p) for p in (
            root/"ai-expert-20261014/semantic-holdout-prospective/holdout-lock-private.json",
            root/"ai-expert-20261015/stage2-real-source-cohort-20261015/stage2-partial4-blind-lock-private.json",
            root/"ai-expert-20261015/stage3-cross-vendor-original-capture/stage3-four-source-only-blind-lock-private.json",
        )],
    }
    return kwargs,latest


def test_stage4_first12_real_source_ids_replay_without_model_data():
    kwargs,original=prior_source_only()
    actual=select_stage4_first_twelve(**kwargs)
    expected=json.loads((original/"stage4-source-ranked-first-twelve-private.json").read_text())
    assert actual==expected
    assert len(actual["selected_discovery_only"])==12
    assert actual["official_cases_verified"]==0
    assert actual["human_gold"]==0
    assert actual["sut_predictions_seen"] is False


def test_changed_original_html_sha_is_not_accepted(tmp_path):
    kwargs,original=prior_source_only()
    for source in original.glob("original-page-*.html"):
        (tmp_path/source.name).write_bytes(source.read_bytes())
    target=tmp_path/"original-page-1.html"
    target.write_bytes(target.read_bytes()+b"tampered after first-party receipt")
    kwargs["original_source_root"]=tmp_path
    with pytest.raises(ValueError,match="SHA changed"):
        select_stage4_first_twelve(**kwargs)


def test_missing_prior_cohort_or_reordered_sources_fail_closed():
    kwargs,_=prior_source_only()
    kwargs["previous_locks"]=kwargs["previous_locks"][:2]
    with pytest.raises(ValueError,match="all three"):
        select_stage4_first_twelve(**kwargs)
    kwargs,_=prior_source_only()
    kwargs["capture_receipt"]=copy.deepcopy(kwargs["capture_receipt"])
    kwargs["capture_receipt"]["source_pages"].reverse()
    with pytest.raises(ValueError,match="URL or ordinal"):
        select_stage4_first_twelve(**kwargs)


def test_pre_registration_change_fails_before_source_use():
    kwargs,_=prior_source_only()
    kwargs["intent"]=copy.deepcopy(kwargs["intent"])
    kwargs["intent"]["planned_max_source_candidate_ids"]=13
    with pytest.raises(ValueError):
        select_stage4_first_twelve(**kwargs)
