"""Reproduce stage4 fixed-rank source IDs from SHA-pinned HTML and earlier locks."""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from scripts.acceptance.capture_r4_stage4_pages23 import (
    SOURCE_ORDER,
    validate_stage4_intent,
)
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    forbid_reuse_of_prior_blind_cohorts,
    forbidden_development_sources,
)
from src.modules.tender_operator_agent_demo.r4_stage4_ranked_cards import (
    stage4_ranked_cards,
)


def select_stage4_first_twelve(
    *, intent: dict, capture_receipt: dict, original_source_root: Path,
    development_audit: dict, previous_locks: list[dict],
) -> dict:
    validate_stage4_intent(intent)
    if len(previous_locks)!=3 or (
        [x["immutable_lock_sha256"] for x in previous_locks]
        !=intent["predecessor_blind_source_lock_shas"]
    ):
        raise ValueError("Stage4 must include all three prior source locks")
    forbidden=forbid_reuse_of_prior_blind_cohorts(
        forbidden_development_sources(development_audit), previous_locks,
    )
    pages=capture_receipt.get("source_pages")
    if (
        capture_receipt.get("intent_sha256")!=intent["immutable_intent_sha256"]
        or not isinstance(pages,list) or len(pages)!=len(SOURCE_ORDER)
    ):
        raise ValueError("Original HTML capture receipt does not match stage4 protocol")
    seen=set(forbidden["notice_numbers"])
    chosen:list[dict]=[]
    rejected:list[dict]=[]
    page_metadata:list[dict]=[]
    registered=datetime.fromisoformat(intent["registered_at_utc"])
    for source_rank,(url,page) in enumerate(zip(SOURCE_ORDER,pages),1):
        if page.get("url")!=url or page.get("source_rank")!=source_rank:
            raise ValueError("Original source URL or ordinal changed")
        if page.get("status")!="TLS_ORIGINAL_SHA_ATTESTED_NOT_SELECTED":
            page_metadata.append({"source_rank":source_rank,"physical_cards":0,
                                  "sha256":None,"status":"SOURCE_UNAVAILABLE"})
            continue
        at=datetime.fromisoformat(page["capture_started_at_utc"])
        if at.tzinfo is None or at<registered:
            raise ValueError("Original source HTML predates locked intent")
        rel=Path(page.get("relative_html") or "")
        if rel.is_absolute() or not rel.parts or ".." in rel.parts:
            raise ValueError("Untrusted source HTML file reference")
        path=(original_source_root/rel).resolve()
        if not path.is_relative_to(original_source_root.resolve()) or not path.is_file():
            raise ValueError("Private first-party HTML source file is missing")
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=page.get("sha256"):
            raise ValueError("First-party source HTML SHA changed after capture")
        cards=stage4_ranked_cards(source_index=source_rank,original_html=raw)
        page_metadata.append({"source_rank":source_rank,
                              "physical_cards":len(cards),"sha256":page["sha256"]})
        for card in cards:
            num=card["registry_number"]
            position={"source_rank":source_rank,"source_card_rank":card["source_card_rank"]}
            if card["law"]!="44-ФЗ" or num is None:
                rejected.append({"source_rank":source_rank,
                                 "card_rank":card["source_card_rank"],
                                 "reason":"NOT_VERIFIABLE_44FZ"})
                continue
            if num in seen:
                rejected.append({"source_rank":source_rank,
                                 "card_rank":card["source_card_rank"],
                                 "reason":"PRIOR_OR_DUPLICATE"})
                continue
            seen.add(num)
            if len(chosen)<intent["planned_max_source_candidate_ids"]:
                chosen.append(dict(position,registry_number=num,html_sha256=page["sha256"]))
            else:
                rejected.append({"source_rank":source_rank,
                                 "card_rank":card["source_card_rank"],
                                 "reason":"OUTSIDE_FIRST_TWELVE"})
    return {
        "intent_sha256":intent["immutable_intent_sha256"],
        "source_cards":page_metadata,
        "selected_discovery_only":chosen,
        "rejected_source_positions":rejected,
        "official_cases_verified":0,
        "sut_predictions_seen":False,
        "human_gold":0,
    }
