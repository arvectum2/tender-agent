"""Read-only corporate procurement card triage, never bid authorization.

A printed future deadline cannot revive a terminal platform status. Indexed
card metadata is provisional, not a live authenticated platform check.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
from urllib.parse import urlsplit


@dataclass(frozen=True)
class CorporateLeadDecision:
    state: str
    reason: str
    bid_ready: bool = False


_TERMINAL = frozenset({
    "завершен", "завершено", "прием заявок завершен",
    "отменен", "отменено", "закрыт", "closed",
    "completed", "cancelled", "canceled",
})
_RECEIVING = frozenset({
    "идет прием заявок", "прием заявок", "accepting applications",
})
_LEGAL_ENTITY = frozenset({"юридическое лицо", "legal entity", "company"})
# A platform's landing page, search result or category page is not a
# procurement notice. This is only a URL-shape check, NOT source attestation.
_ORIGINAL_CARD_PATHS = {
    "workspace.ru": r"/tenders/[a-z0-9][a-z0-9-]*-\\d{5}/?",
    "www.b2b-center.ru": r"/market/[a-z0-9][a-z0-9-]*/tender-\\d+/?",
    "b2b-center.ru": r"/market/[a-z0-9][a-z0-9-]*/tender-\\d+/?",
}


def _normalized(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.casefold().replace("ё", "е").split())


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return result if result.tzinfo is not None and result.utcoffset() is not None else None


def _deadline(value: object) -> tuple[date | datetime | None, bool]:
    if not isinstance(value, str):
        return None, False
    if len(value) == 10:
        try:
            return date.fromisoformat(value), False
        except ValueError:
            return None, False
    return _timestamp(value), True


def triage_corporate_card(
    card: Mapping[str, object],
    *,
    checked_at: datetime,
    max_evidence_age: timedelta = timedelta(hours=48),
) -> CorporateLeadDecision:
    """Classify public evidence, not eligibility, current ETP bookability or GO.

    source_observed_at is the time of observation of the original platform
    status, not when an intermediary indexed a search snippet.
    """
    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise ValueError("checked_at must be timezone-aware")
    if max_evidence_age <= timedelta(0):
        raise ValueError("max_evidence_age must be positive")

    url = card.get("source_url")
    if not isinstance(url, str):
        return CorporateLeadDecision("REVIEW_REQUIRED", "missing_platform_url")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return CorporateLeadDecision("REVIEW_REQUIRED", "unsupported_original_platform_url")
    if (
        parts.scheme != "https"
        or parts.username or parts.password or port is not None
        or parts.hostname not in _ORIGINAL_CARD_PATHS
        or re.fullmatch(_ORIGINAL_CARD_PATHS[parts.hostname], parts.path) is None
    ):
        return CorporateLeadDecision("REVIEW_REQUIRED", "unsupported_original_platform_url")

    status = _normalized(card.get("platform_status"))
    if status in _TERMINAL:
        return CorporateLeadDecision("CLOSED", "terminal_platform_status")

    if _normalized(card.get("organizer_type")) not in _LEGAL_ENTITY:
        return CorporateLeadDecision("REVIEW_REQUIRED", "legal_entity_buyer_unverified")

    observed = _timestamp(card.get("source_observed_at"))
    if observed is None:
        return CorporateLeadDecision("REVIEW_REQUIRED", "source_status_timestamp_missing")
    freshness = checked_at - observed
    if freshness < timedelta(0) or freshness > max_evidence_age:
        return CorporateLeadDecision("REVIEW_REQUIRED", "source_status_stale_or_in_future")
    if status not in _RECEIVING:
        return CorporateLeadDecision("REVIEW_REQUIRED", "platform_receiving_status_unverified")

    deadline, has_time = _deadline(card.get("submission_deadline"))
    if deadline is None:
        return CorporateLeadDecision("REVIEW_REQUIRED", "deadline_missing_or_invalid")
    if has_time and isinstance(deadline, datetime):
        if deadline <= checked_at:
            return CorporateLeadDecision("CLOSED", "deadline_elapsed")
    elif isinstance(deadline, date):
        # Compare in the operator-specified time zone: a date alone does not
        # establish whether a same-day cutoff is still in the future.
        local_day = checked_at.astimezone(observed.tzinfo).date()
        if deadline < local_day:
            return CorporateLeadDecision("CLOSED", "deadline_date_elapsed")
        if deadline == local_day:
            return CorporateLeadDecision("REVIEW_REQUIRED", "same_day_cutoff_time_unknown")

    return CorporateLeadDecision("PUBLIC_CANDIDATE_ONLY", "requires_fresh_platform_and_eligibility_check")
