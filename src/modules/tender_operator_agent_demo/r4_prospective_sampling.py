"""Deterministic future-cohort preregistration; discovery is NOT official EIS.

Only opaque identifiers and dates are selected. Content/legal semantics and
Tender Agent predictions must not be consulted to decide who enters holdout.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from src.modules.benchmark_pipeline.contract import canonical_sha256
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    NUMBER,
    HoldoutLeakageError,
)

KNOWN_PAGES = (
    "https://tendigo.ru/tenders/razrabotka-po/",
    "https://tendigo.ru/tenders/razrabotka-saytov/",
)


def _aware(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Prospective source times require timezone")
    return parsed


def preregister_sampling_intent(
    *,
    registered_at_utc: str,
    existing_blind_lock_sha256: str,
    target_new_cases: int = 12,
) -> dict[str, Any]:
    """Select first N previously unknown visible cases; no hand-picked substitutes."""
    _aware(registered_at_utc)
    if not re.fullmatch(r"[a-f0-9]{64}", existing_blind_lock_sha256):
        raise ValueError("Previous blind lock digest required")
    if target_new_cases < 3 or target_new_cases > 40:
        raise ValueError("Holdout target outside bounded sampling range")
    result: dict[str, Any] = {
        "registered_at_utc": registered_at_utc,
        "target_new_cases": target_new_cases,
        "page_order": list(KNOWN_PAGES),
        "selection_method": "FIRST_VISIBLE_44FZ_19_DIGIT_UNSEEN_BY_SOURCE_PAGE_AND_RANK",
        "source_scope": "IT_SERVICE_DEVELOPMENT_DISCOVERY_ONLY_NOT_OFFICIAL_EIS",
        "prior_blind_lock_sha256": existing_blind_lock_sha256,
        "fail_policy": (
            "Record incomplete/404/undocumented sources as UNAVAILABLE; "
            "exclude prior development and blind cases; official getDocsIP "
            "and all raw binaries SHA verified before declaring real cohort; "
            "no backfill outside preregistered page/rank order."
        ),
        "candidate_sources_only": True,
        "gold_labels_authorized": False,
        "sut_inference_authorized": False,
    }
    result["immutable_intent_sha256"] = canonical_sha256(result)
    return result


def validate_sampling_intent(intent: dict[str, Any]) -> None:
    actual = intent.get("immutable_intent_sha256")
    expected = canonical_sha256({
        key: value for key, value in intent.items() if key != "immutable_intent_sha256"
    })
    if actual != expected or intent["page_order"] != list(KNOWN_PAGES):
        raise HoldoutLeakageError("Prospective sampling plan was changed after registration")
    _aware(intent["registered_at_utc"])
    if intent["sut_inference_authorized"] is not False:
        raise HoldoutLeakageError("Prospective sampling must be pre-SUT")


def select_source_only_candidates(
    *, intent: dict[str, Any],
    snapshots: list[dict[str, Any]],
    forbidden_numbers: set[str],
) -> dict[str, Any]:
    """Only accept fully sourced newer snapshots; never backfill cherry-picked IDs."""
    validate_sampling_intent(intent)
    by_page = {page["url"]: page for page in snapshots}
    if len(by_page) != len(snapshots) or set(by_page) != set(intent["page_order"]):
        raise ValueError("Missing, extra, or duplicate preregistered discovery pages")
    seen = set(forbidden_numbers)
    accepted: list[str] = []
    rejected: list[dict[str, str]] = []
    for url in intent["page_order"]:
        page = by_page[url]
        if page.get("status") != "SOURCE_FETCH_VERIFIED":
            raise ValueError("Source snapshot not verified; do not invent candidate IDs")
        if _aware(page["captured_at_utc"]) < _aware(intent["registered_at_utc"]):
            raise ValueError("Snapshot predates prospective selection intent")
        rows = page.get("rows")
        if not isinstance(rows, list):
            raise TypeError("Unverified discovery list")
        ranks: set[int] = set()
        for row in rows:
            rank = row["visible_rank"]
            if type(rank) is not int or rank < 1 or rank in ranks:
                raise ValueError("Missing/duplicated source rank")
            ranks.add(rank)
        if ranks != set(range(1, len(rows) + 1)):
            raise ValueError("Incomplete source rank order")
        for row in sorted(rows, key=lambda item: item["visible_rank"]):
            no = row.get("registry_number")
            if row.get("law") != "44-ФЗ":
                rejected.append({"reason": "NOT_44FZ", "notice_ref": str(no)})
                continue
            if not isinstance(no, str) or NUMBER.fullmatch(no) is None:
                rejected.append({"reason": "NO_19_DIGIT_REGISTRY_NUMBER", "notice_ref": str(no)})
                continue
            if no in seen:
                rejected.append({"reason": "PRIOR_OR_DUPLICATE", "notice_ref": no})
                continue
            seen.add(no)
            if len(accepted) < intent["target_new_cases"]:
                accepted.append(no)
            else:
                rejected.append({"reason": "OUTSIDE_REGISTERED_TARGET", "notice_ref": no})
    return {
        "intent_sha256": intent["immutable_intent_sha256"],
        "discovery_source_count": len(snapshots),
        "target_new_cases": intent["target_new_cases"],
        "discovery_candidate_numbers": accepted,
        "rejected_source_rows": rejected,
        "selection_status": (
            "DISCOVERY_ONLY_PRE_OFFICIAL_ATTESTATION"
            if len(accepted) == intent["target_new_cases"]
            else "UNDERFILLED_DISCOVERY_NO_UNREGISTERED_BACKFILL"
        ),
        "official_original_eis_cases_verified": 0,
        "legal_gold_cases": 0,
        "sut_inference_authorized": False,
        "bid_ready": False,
    }
