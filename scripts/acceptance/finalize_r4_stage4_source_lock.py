"""Freeze first four provably independent official EIS cases from fixed twelve.

No reinterpretation of legal documents or SUT calls. Replays immutable source
discovery from SHA-attested original HTML and requires all prior blind locks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.acceptance.prepare_r4_unseen_semantic_holdout import prepare_real_holdout
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    forbid_reuse_of_prior_blind_cohorts,
    forbidden_development_sources,
)
from src.modules.tender_operator_agent_demo.r4_stage3_independence_filter import (
    filter_attested_candidates_by_independence,
)
from src.modules.tender_operator_agent_demo.r4_stage4_source_selection import (
    select_stage4_first_twelve,
)


def finalize_stage4_source_only(
    *, intent: dict, capture: dict, actual_discovery: dict,
    original_html_root: Path, official_archive_root: Path,
    actual_official_cases: list[dict], development_audit: dict,
    three_previous_locks: list[dict], freeze_at_utc: str,
) -> tuple[dict, dict]:
    if not isinstance(three_previous_locks, list) or len(three_previous_locks) != 3:
        raise ValueError("All three previous independent locks are mandatory")
    replay=select_stage4_first_twelve(
        intent=intent, capture_receipt=capture,original_source_root=original_html_root,
        development_audit=development_audit,previous_locks=three_previous_locks,
    )
    if replay != actual_discovery or len(replay["selected_discovery_only"])!=12:
        raise ValueError("Prospective source order changed after original HTML capture")
    excluded=forbid_reuse_of_prior_blind_cohorts(
        forbidden_development_sources(development_audit),three_previous_locks,
    )
    with_id=dict(replay,source_intent_sha256=replay["intent_sha256"])
    source_audit=filter_attested_candidates_by_independence(
        immutable_discovery=with_id, official_cases=actual_official_cases,
        previously_protected_numbers=excluded["notice_numbers"],
        previously_protected_original_sha256=excluded["binary_sha256"],
        previously_protected_zip_sha256=excluded["zip_sha256"],
        previously_protected_xml_sha256=excluded["xml_sha256"],
        expected_candidate_count=12,
    )
    accepted=source_audit["accepted_source_only_cases"]
    target=intent["target_new_verified_cases"]
    if target!=4:
        raise ValueError("Frozen stage4 target cannot be changed")
    if len(accepted)<target:
        raise ValueError("Underfilled independent stage4 cohort; cannot fake four cases")
    first_four=accepted[:target]
    # Fully independent official source validation is repeated by canonical
    # immutable lock constructor; never trust only the first-party receipt label.
    lock=prepare_real_holdout(
        first_four, source_root=official_archive_root,
        development_audit=development_audit,
        source_set_id="R4_STAGE4_CROSSVENDOR_FIRST_FOUR_20261015",
        frozen_at_utc=freeze_at_utc,
        prior_blind_locks=three_previous_locks,
    )
    if lock["case_count"]!=target:
        raise ValueError("Canonical source lock is incomplete")
    if {x["registry_number"] for x in lock["cases"]}!={
        x["registry_number"] for x in first_four
    }:
        raise ValueError("Unexpected official source identity after lock")
    audit={
        "source_intent_sha256":intent["immutable_intent_sha256"],
        "all_twelve_source_candidates_attempted":len(actual_official_cases)==12,
        "official_source_complete_count":sum(
            x.get("status")=="ALL_OFFICIAL_EIS_ORIGINALS_VERIFIED"
            for x in actual_official_cases
        ),
        "source_independent_count_before_target_cap":len(accepted),
        "source_locked_count":lock["case_count"],
        "first_four_selected_source_order":[x["registry_number"] for x in first_four],
        "independent_but_not_in_frozen_target_count":len(accepted)-target,
        "excluded_source_positions":source_audit["excluded_cases_in_source_order"],
        "raw_sha_verified_locked_original_count":sum(
            len(x["documents"]) for x in first_four
        ),
        "source_lock_sha256":lock["immutable_lock_sha256"],
        "gold_signed_count":0,
        "sut_ran":False,
        "bid_ready":False,
    }
    return lock,audit


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--intent",type=Path,required=True)
    ap.add_argument("--capture-receipt",type=Path,required=True)
    ap.add_argument("--discovery-receipt",type=Path,required=True)
    ap.add_argument("--original-html-root",type=Path,required=True)
    ap.add_argument("--official-source-root",type=Path,required=True)
    ap.add_argument("--official-receipt",type=Path,required=True)
    ap.add_argument("--development-audit",type=Path,required=True)
    ap.add_argument("--prior-blind-lock",type=Path,action="append",required=True)
    ap.add_argument("--output-private-lock",type=Path,required=True)
    ap.add_argument("--output-private-audit",type=Path,required=True)
    ap.add_argument("--output-private-candidates",type=Path,required=True)
    a=ap.parse_args()
    outputs=(a.output_private_lock,a.output_private_audit,a.output_private_candidates)
    if any(p.exists() for p in outputs):
        raise ValueError("Cannot overwrite frozen stage4 original-source receipts")
    read=lambda p:json.loads(p.read_text())
    official=read(a.official_receipt)["cases"]
    lock, audit=finalize_stage4_source_only(
        intent=read(a.intent),
        capture=read(a.capture_receipt),
        actual_discovery=read(a.discovery_receipt),
        original_html_root=a.original_html_root,
        official_archive_root=a.official_source_root,
        actual_official_cases=official,
        development_audit=read(a.development_audit),
        three_previous_locks=[read(p) for p in a.prior_blind_lock],
        freeze_at_utc=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    chosen=set(audit["first_four_selected_source_order"])
    candidates=[x for x in official if x["registry_number"] in chosen]
    for target,payload in zip(outputs,(lock,audit,candidates)):
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
        print("SOURCE_ONLY_PRIVATE_SHA",target.name,hashlib.sha256(target.read_bytes()).hexdigest())
    print("STAGE4_IMMUTABLE_FIRST_FOUR_BLIND_LOCKED",lock["case_count"],"ORIGINALS",audit["raw_sha_verified_locked_original_count"],"SHA",lock["immutable_lock_sha256"])


if __name__=="__main__":
    main()
