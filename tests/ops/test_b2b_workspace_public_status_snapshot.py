"""No-network tests, with frozen primary read-only snapshot safety assertions."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.ops.b2b_workspace_public_status_snapshot import (
    PublicSourceError,
    capture,
    classify_original_page,
    date_from_original,
    validated_urls,
)

_ROOT = Path(__file__).resolve().parents[2]
_URL = "https://workspace.ru/tenders/fixture-tender-19043/"
_NOW = datetime(2026, 10, 18, 13, 35, tzinfo=UTC)


def sample(status="Идет прием заявок", organizer="Юридическое лицо",
           deadline="31 октября 2026", budget="200 000 - 800 000 рублей"):
    return f"""
    <html><body>
    <div class="tendercart-type__status-public ">{status}</div>
    <h1 class="title">Тестовый корпоративный сайт</h1>
    <div class="b-tender__info-item-title">Бюджет:</div>
    <div class="b-tender__info-item-text">{budget}</div>
    <div class="b-tender__info-item-title">Крайний срок приема заявок:</div>
    <div class="b-tender__info-item-text">{deadline}</div>
    <div class="card-info__title">Oрганизатор</div><p class="card-info__desc">{organizer}</p>
    </body></html>""".encode()


def test_genuine_public_company_card_remains_candidate_only():
    x = classify_original_page(sample(), source_url=_URL, observed_at=_NOW)
    assert x["source_gate"] == "PUBLIC_CORPORATE_CANDIDATE_ONLY"
    assert x["source_html_sha256"] and len(x["source_html_sha256"]) == 64
    assert x["platform_status"] == "Идет прием заявок"
    assert x["printed_deadline_date"] == "2026-10-31"
    assert x["printed_deadline_exact_time"] == "UNKNOWN"
    assert x["commercial_go"] is False
    assert x["authenticated_legal_entity_bidder_verified"] is False
    assert x["self_selected_reply_requires_pro_or_invitation"] == "OWNER_ACCOUNT_CONFIRMATION_REQUIRED"


@pytest.mark.parametrize("terminal", ["Завершён", "Прием заявок завершен"])
def test_platform_closed_outweighs_future_printed_deadline(terminal):
    x = classify_original_page(sample(status=terminal), source_url=_URL, observed_at=_NOW)
    assert x["source_gate"] == "EXCLUDE_TERMINAL_PLATFORM_STATUS"
    assert x["public_corporate_candidate"] is False


def test_private_buyer_not_counted_even_with_corporate_title():
    x = classify_original_page(
        sample(organizer="Частное лицо"), source_url=_URL, observed_at=_NOW
    )
    assert x["source_gate"] == "EXCLUDE_PRIVATE_BUYER"
    assert x["public_corporate_candidate"] is False


def test_historical_date_does_not_resurrect_a_public_active_marker():
    x = classify_original_page(
        sample(deadline="17 октября 2026"), source_url=_URL, observed_at=_NOW
    )
    assert x["source_gate"] == "EXCLUDE_PAST_PRINTED_DEADLINE"


@pytest.mark.parametrize("bad", [
    "October 31 2026", "32 октября 2026", "01 бахмутя 2026",
    "31 октября 2026 00:00", "",
])
def test_non_original_or_ambiguous_deadline_fails_closed(bad):
    with pytest.raises(PublicSourceError):
        date_from_original(bad)


@pytest.mark.parametrize("url", [
    "http://workspace.ru/tenders/item-19043/",
    "https://workspace.ru.evil.example/tenders/item-19043/",
    "https://workspace.ru/tenders/item-19043/?redirect=x",
    "https://workspace.ru/tenders/../../../etc-19043/",
    "https://workspace.ru/tenders/",
    "https://other.example/tenders/item-19043/",
])
def test_non_original_urls_rejected_before_network(url):
    with pytest.raises(PublicSourceError):
        validated_urls([url])


def test_duplicate_url_rejected_before_network():
    with pytest.raises(PublicSourceError):
        validated_urls([_URL, _URL])


def test_duplicate_ids_same_platform_fail_closed():
    with pytest.raises(PublicSourceError, match="duplicate tender id"):
        capture(
            [_URL, "https://workspace.ru/tenders/different-title-19043/"],
            fetch=lambda _: sample(),
            now=_NOW,
        )


def test_bad_page_missing_status_and_organizer_fail_closed():
    with pytest.raises(PublicSourceError):
        classify_original_page(b"<h1>Title</h1>", source_url=_URL, observed_at=_NOW)


def test_transport_errors_produce_only_unknown_non_candidates():
    result = capture(
        [_URL], fetch=lambda _: (_ for _ in ()).throw(OSError("offline")),
        now=_NOW,
    )
    assert result["firstparty_http200_cards_parsed"] == 0
    assert result["public_corporate_source_candidates"] == 0
    assert result["items"][0]["source_gate"] == "UNKNOWN_FAIL_CLOSED"
    assert result["strict_owner_qualified_bid_opportunities"] == 0


def test_public_20261018_snapshot_21_distinct_no_invented_bid_go():
    j = json.loads((
        _ROOT / "docs/roadmap/b2b_workspace_original_current_2026-10-18.json"
    ).read_text())
    urls = json.loads((
        _ROOT / "docs/roadmap/b2b_workspace_original_watchlist_2026-10-18.json"
    ).read_text())
    assert len(validated_urls(urls)) == j["total_explicit_prior_or_new_watchlist_ids"] == 21
    assert len(j["items"]) == 21
    assert len({row["id"] for row in j["items"]}) == 21
    assert sum(row["public_corporate_candidate"] for row in j["items"]) == j[
        "public_corporate_source_candidates"
    ] == 9
    assert j["firstparty_http200_cards_parsed"] == 21
    assert j["strict_owner_qualified_bid_opportunities"] == 0
    assert j["target_15_20_fully_qualified_met"] is False
    assert j["commercial_external_submissions"] == 0
    assert j["paid_access_purchases"] == 0
    for row in j["items"]:
        assert row["source_gate"] in {
            "PUBLIC_CORPORATE_CANDIDATE_ONLY",
            "EXCLUDE_PRIVATE_BUYER",
            "EXCLUDE_TERMINAL_PLATFORM_STATUS",
            "EXCLUDE_PAST_PRINTED_DEADLINE",
            "UNKNOWN_FAIL_CLOSED",
        }
        assert row["authenticated_legal_entity_bidder_verified"] is False
        assert row["commercial_go"] is False
        assert row["source_http_status"] == 200
        assert len(row["source_html_sha256"]) == 64
    by_id = {row["id"]: row for row in j["items"]}
    assert by_id["workspace-19003"]["platform_status"] == "Завершён"
    assert by_id["workspace-19003"]["printed_deadline_date"] == "2026-10-21"
    assert by_id["workspace-19003"]["public_corporate_candidate"] is False
    assert by_id["workspace-19035"]["organizer_type"] == "Частное лицо"
    assert by_id["workspace-19052"]["public_corporate_candidate"] is False


def test_moscow_calendar_date_does_not_lag_utc_when_deadline_expires():
    # 21:30 UTC on 18 October is already 19 October in Moscow.
    result = classify_original_page(
        sample(deadline="18 октября 2026"), source_url=_URL,
        observed_at=datetime(2026, 10, 18, 21, 30, tzinfo=UTC),
    )
    assert result["compared_date_in_moscow"] == "2026-10-19"
    assert result["source_gate"] == "EXCLUDE_PAST_PRINTED_DEADLINE"


def test_naive_research_time_is_rejected():
    with pytest.raises(PublicSourceError, match="observation_without_timezone"):
        classify_original_page(
            sample(), source_url=_URL, observed_at=datetime(2026, 10, 18)  # noqa: DTZ001 - deliberate invalid time test
        )
