"""Pre-SUT source-only selection of first 8 distinct stage3 44-FZ IDs.

Takes immutable original HTML, two previously frozen locks and development
source identities. Does not examine model predictions or legal clauses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from scripts.acceptance.capture_r4_stage3_preregistered_sources import (
    SOURCE_URLS,
    validate_stage3_plan,
)
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    forbid_reuse_of_prior_blind_cohorts,
    forbidden_development_sources,
    verify_cohort_lock,
)
from src.modules.tender_operator_agent_demo.r4_stage3_crossvendor_cards import (
    parse_stage3_cards,
)


def select_stage3_candidates(
    *,
    intent: dict,
    original_capture_receipt: dict,
    private_capture_root: Path,
    development_audit: dict,
    previous_locks: list[dict],
) -> dict:
    validate_stage3_plan(intent)
    if len(previous_locks) != 2:
        raise ValueError("All two previous blind locks are mandatory")
    for previous in previous_locks:
        verify_cohort_lock(previous)
    actual_locks = [x["immutable_lock_sha256"] for x in previous_locks]
    if actual_locks != intent["prior_immutable_blind_lock_sha256"]:
        raise ValueError("Pre-registered earlier blind locks differ")
    excluded = forbid_reuse_of_prior_blind_cohorts(
        forbidden_development_sources(development_audit), previous_locks,
    )
    pages = original_capture_receipt.get("source_capture_status")
    if (
        original_capture_receipt.get("stage3_preregistered_intent_sha256")
        != intent["immutable_intent_sha256"]
        or not isinstance(pages, list)
        or len(pages) != len(SOURCE_URLS)
    ):
        raise ValueError("Live original source receipt does not match intent")
    selected = []
    rejected = []
    seen = set(excluded["notice_numbers"])
    page_results = []
    for rank, (url, source) in enumerate(zip(SOURCE_URLS, pages), 1):
        if source.get("url") != url or source.get("source_rank") != rank:
            raise ValueError("Wrong original source URL/rank")
        if source.get("status") != "RAW_FIRST_PARTY_TLS_HTML_SHA_LOCKED_NOT_PARSED":
            page_results.append({"source_rank": rank, "source_status": "UNAVAILABLE", "source_cards": 0})
            continue
        stamp = datetime.fromisoformat(source["started_at_utc"])
        if stamp.tzinfo is None or stamp < datetime.fromisoformat(intent["registered_at_utc"]):
            raise ValueError("Original source HTML predates prospective lock")
        path = Path(source.get("body_relative_path") or "")
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise ValueError("Unsafe original source receipt path")
        original = (private_capture_root / path).resolve()
        if not original.is_relative_to(private_capture_root.resolve()) or not original.is_file():
            raise ValueError("Original vendor HTML missing")
        raw = original.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source.get("body_sha256"):
            raise ValueError("Source HTML was changed after immutable capture")
        cards = parse_stage3_cards(url, raw)
        page_results.append({"source_rank":rank,"source_status":"SHA_VERIFIED","source_cards":len(cards)})
        for card in cards:
            number = card["registry_number"]
            if card["law"] != "44-ФЗ" or number is None:
                rejected.append({"source_rank": rank, "card_rank":card["source_card_rank"], "reason":"NOT_VERIFIED_44FZ_ID"})
                continue
            if number in seen:
                rejected.append({"source_rank": rank, "card_rank":card["source_card_rank"], "reason":"PREVIOUS_OR_DUPLICATE"})
                continue
            seen.add(number)
            if len(selected) < intent["target_new_cases"]:
                selected.append({
                    "registry_number": number,
                    "source_rank": rank,
                    "source_card_rank": card["source_card_rank"],
                    "html_sha256": source["body_sha256"],
                })
            else:
                rejected.append({"source_rank": rank, "card_rank":card["source_card_rank"], "reason":"OUTSIDE_FIXED_EIGHT"})
    return {
        "source_intent_sha256": intent["immutable_intent_sha256"],
        "previous_blind_locks_sha256": actual_locks,
        "source_pages": page_results,
        "target_new_cases": intent["target_new_cases"],
        "selected_discovery_only": selected,
        "excluded_source_positions": rejected,
        "selection_status": "DISCOVERY_ONLY_NEEDS_OFFICIAL_EIS_ORIGINALS" if len(selected)==8 else "UNDERFILLED_NO_BACKFILL",
        "official_eis_originals_verified": 0,
        "signed_external_gold": 0,
        "sut_inference_allowed": False,
        "bid_ready": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intent", type=Path, required=True)
    ap.add_argument("--original-capture-receipt", type=Path, required=True)
    ap.add_argument("--private-capture-root", type=Path, required=True)
    ap.add_argument("--development-audit", type=Path, required=True)
    ap.add_argument("--previous-blind-lock", type=Path, action="append", required=True)
    ap.add_argument("--private-output", type=Path, required=True)
    args=ap.parse_args()
    if args.private_output.exists():
        raise ValueError("Cannot overwrite stage3 immutable selected candidates")
    result=select_stage3_candidates(
        intent=json.loads(args.intent.read_text()),
        original_capture_receipt=json.loads(args.original_capture_receipt.read_text()),
        private_capture_root=args.private_capture_root,
        development_audit=json.loads(args.development_audit.read_text()),
        previous_locks=[json.loads(p.read_text()) for p in args.previous_blind_lock],
    )
    args.private_output.parent.mkdir(parents=True,exist_ok=True)
    args.private_output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("REGISTERED_STAGE3_SOURCE_ONLY_SELECTED",len(result["selected_discovery_only"]),"OF",result["target_new_cases"])
    print("NO_SUT_NO_GOLD_NO_OFFICIAL_ATTESTATION_YET")


if __name__=="__main__":
    main()
