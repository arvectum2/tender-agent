"""A closed platform card beats a future printed deadline."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.tender_research.corporate_lead_gate import triage_corporate_card

NOW = datetime(2026, 10, 13, 9, 17, tzinfo=timezone(timedelta(hours=3)))


def card(**updates):
    data = {
        "source_url": "https://workspace.ru/tenders/internet-portal-19004/",
        "organizer_type": "Юридическое лицо",
        "platform_status": "Идет прием заявок",
        "source_observed_at": "2026-10-13T09:15:00+03:00",
        "submission_deadline": "2026-10-14",
    }
    data.update(updates)
    return data


@pytest.mark.parametrize("status", [
    "Завершён", "Прием заявок завершен", "Отменён", "Closed",
    "Completed", "Cancelled",
])
def test_terminal_status_outranks_future_deadline(status):
    result = triage_corporate_card(card(platform_status=status), checked_at=NOW)
    assert (result.state, result.reason, result.bid_ready) == (
        "CLOSED", "terminal_platform_status", False,
    )


def test_public_open_future_day_is_only_unverified_candidate():
    result = triage_corporate_card(card(), checked_at=NOW)
    assert result.state == "PUBLIC_CANDIDATE_ONLY"
    assert result.bid_ready is False


def test_same_day_date_only_cutoff_remains_unknown():
    result = triage_corporate_card(card(submission_deadline="2026-10-13"), checked_at=NOW)
    assert result.state == "REVIEW_REQUIRED"
    assert result.reason == "same_day_cutoff_time_unknown"


def test_same_day_with_explicit_future_time_still_not_bid_ready():
    result = triage_corporate_card(
        card(submission_deadline="2026-10-13T15:00:00+03:00"),
        checked_at=NOW,
    )
    assert result.state == "PUBLIC_CANDIDATE_ONLY"
    assert result.bid_ready is False


@pytest.mark.parametrize("deadline", ["2026-10-12", "2026-10-13T08:00:00+03:00"])
def test_expired_deadline_never_open(deadline):
    assert triage_corporate_card(card(submission_deadline=deadline), checked_at=NOW).state == "CLOSED"


@pytest.mark.parametrize(("key", "value", "reason"), [
    ("organizer_type", "Частное лицо", "legal_entity_buyer_unverified"),
    ("organizer_type", "", "legal_entity_buyer_unverified"),
    ("platform_status", "Опубликован", "platform_receiving_status_unverified"),
    ("platform_status", "", "platform_receiving_status_unverified"),
    ("source_observed_at", "", "source_status_timestamp_missing"),
    ("source_observed_at", "2026-10-09T12:00:00+03:00", "source_status_stale_or_in_future"),
    ("source_observed_at", "2026-10-14T12:00:00+03:00", "source_status_stale_or_in_future"),
    ("submission_deadline", "unknown", "deadline_missing_or_invalid"),
])
def test_incomplete_or_stale_evidence_fails_closed(key, value, reason):
    result = triage_corporate_card(card(**{key: value}), checked_at=NOW)
    assert result.state == "REVIEW_REQUIRED"
    assert result.reason == reason
    assert result.bid_ready is False


@pytest.mark.parametrize("url", [
    "http://workspace.ru/tenders/19004",
    "https://workspace.ru.evil.example/tenders/19004",
    "https://example.com/tenders/19004",
    "https://workspace.ru/private/19004",
    "https://alice:secret@workspace.ru/tenders/19004",
])
def test_only_exact_original_https_hosts_accepted(url):
    result = triage_corporate_card(card(source_url=url), checked_at=NOW)
    assert result.state == "REVIEW_REQUIRED"
    assert result.reason == "unsupported_original_platform_url"


def test_naive_check_time_rejected():
    with pytest.raises(ValueError, match="timezone"):
        triage_corporate_card(card(), checked_at=datetime.fromisoformat("2026-10-13T09:17:00"))


def test_terminal_status_does_not_require_live_clock_but_stays_closed():
    result = triage_corporate_card(
        card(platform_status="Завершён", source_observed_at="2026-10-09T09:00:00+03:00"),
        checked_at=NOW,
    )
    assert result.state == "CLOSED"
    assert result.bid_ready is False
