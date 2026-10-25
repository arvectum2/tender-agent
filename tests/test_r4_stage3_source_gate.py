"""Test stage3 preregistered capture/selection without SUT or legal gold."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from scripts.acceptance.capture_r4_stage3_preregistered_sources import (
    capture_stage3_sources,
    validate_stage3_plan,
)
from scripts.acceptance.select_r4_stage3_crossvendor_candidates import (
    select_stage3_candidates,
)


def intent():
    return json.loads(Path(
        "docs/acceptance/data/TA_R4_STAGE3_CROSS_VENDOR_PROSPECTIVE_INTENT_2026-10-15.json"
    ).read_text())


def test_original_public_preregistration_is_immutable_and_blind():
    plan=intent()
    validate_stage3_plan(plan)
    assert plan["target_new_cases"]==8
    assert plan["sut_inference_authorized"] is False
    assert plan["gold_labels_authorized"] is False
    changed=copy.deepcopy(plan)
    changed["source_page_order"].reverse()
    with pytest.raises(ValueError,match="tampered"):
        validate_stage3_plan(changed)
    changed=copy.deepcopy(plan)
    changed["target_new_cases"]=12
    with pytest.raises(ValueError,match="tampered"):
        validate_stage3_plan(changed)


def test_failed_tls_sources_do_not_fabricate_or_backdate(monkeypatch,tmp_path):
    from scripts.acceptance import capture_r4_stage3_preregistered_sources as mod

    def reject(*_args,**_kwargs):
        raise TimeoutError("source unavailable")

    monkeypatch.setattr(mod,"urlopen",reject)
    result=capture_stage3_sources(intent(),tmp_path/"source-only")
    assert result["successful_original_html"]==0
    assert result["official_eis_cases_verified"]==0
    assert result["model_predictions_seen"] is False
    assert all(x["status"]=="SOURCE_UNAVAILABLE" for x in result["source_capture_status"])
    with pytest.raises(ValueError,match="overwrite"):
        capture_stage3_sources(intent(),tmp_path/"source-only")


def test_real_private_source_selection_is_sha_bound_and_pre_sut(tmp_path):
    root = os.environ.get("TA_PRIVATE_R4_SOURCE_ROOT")
    if not root:
        pytest.skip("Private first-party source archives only available on authorized Mac")
    evidence=Path(root)
    stage3=evidence/"ai-expert-20261015"/"stage3-cross-vendor-original-capture"
    prior=evidence/"ai-expert-20261014"/"semantic-holdout-prospective"/"holdout-lock-private.json"
    stage2=evidence/"ai-expert-20261015"/"stage2-real-source-cohort-20261015"/"stage2-partial4-blind-lock-private.json"
    if not stage3.is_dir() or not prior.is_file() or not stage2.is_file():
        pytest.skip("Current private stage3 receipts unavailable")
    args={
        "intent":intent(),
        "original_capture_receipt":json.loads(
            (stage3/"source-only-capture-receipt-private.json").read_text()
        ),
        "private_capture_root":stage3,
        "development_audit":json.loads(Path(
            "docs/acceptance/data/TDP_R4_20_TRUE_COMPETITIVE_ORIGINAL_SEMANTIC_AUDIT_2026-10-14.json"
        ).read_text()),
        "previous_locks":[json.loads(p.read_text()) for p in (prior,stage2)],
    }
    actual=select_stage3_candidates(**args)
    frozen=json.loads((stage3/"selected-stage3-8-discovery-only-private.json").read_text())
    assert actual==frozen
    assert len(actual["selected_discovery_only"])==8
    assert actual["official_eis_originals_verified"]==0
    assert actual["signed_external_gold"]==0
    # Copy and tamper a source page without changing its private SHA receipt.
    for source in stage3.glob("source-*.html"):
        (tmp_path/source.name).write_bytes(source.read_bytes())
    first=tmp_path/"source-1.html"
    first.write_bytes(first.read_bytes()+b"changed after capture")
    args["private_capture_root"]=tmp_path
    with pytest.raises(ValueError,match="changed"):
        select_stage3_candidates(**args)
