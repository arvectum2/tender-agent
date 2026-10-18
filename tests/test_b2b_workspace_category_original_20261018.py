"""B2B original-card discovery never attests authenticated LLC bidding rights."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.acceptance.discover_workspace_original_it_20261018 import (
    INDEX_URLS,
    PRIORITY_SOURCE_ANCHORS,
    _canonical_card,
    discover_exact_cards,
    evaluate_original_card,
)

SNAPSHOT = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "docs/roadmap/b2b_workspace_category_original_2026-10-18.json"
    ).read_text(encoding="utf-8")
)
NOW = datetime(2026, 10, 18, 7, 0, tzinfo=UTC)
ORIGINAL = "https://workspace.ru/tenders/novyy-dizayn-sayta-detskih-tovarov-19012/"


def _html(
    *,
    title: str = "Новый дизайн сайта детских товаров",
    status: str = "Идет прием заявок",
    visibility: str = "public",
    buyer: str = "Юридическое лицо",
    due: str = "19 октября 2026",
    original_requirements: bool = True,
) -> bytes:
    extra = " ".join(PRIORITY_SOURCE_ANCHORS["19012"]) if original_requirements else "Описание отсутствует"
    return (
        "<html><head><title>Оригинал</title></head><body>"
        f"<h1>{title}</h1>"
        f'<div class="tendercart-type__status-public">{status}</div>'
        f'<span class="reference _{visibility}">Публичный</span>'
        f"<section>{extra}</section>"
        f"<div>Крайний срок приема заявок: {due}</div>"
        f"<aside>Oрганизатор: {buyer}</aside>"
        + "A" * 700 + "</body></html>"
    ).encode("utf-8")


def _evaluate(body: bytes, **kwargs) -> dict:
    return evaluate_original_card(
        number=kwargs.get("number", "19012"),
        slug=kwargs.get("slug", "novyy-dizayn-sayta-detskih-tovarov"),
        original_url=kwargs.get("url", ORIGINAL),
        body=body,
        observed=kwargs.get("observed", NOW),
        categories=kwargs.get("categories", ("WEB",)),
    )


def test_three_exact_index_urls_allow_deduped_original_cards_only():
    assert len(INDEX_URLS) == 3
    index = INDEX_URLS[0][1]
    body = (
        "<html>" + "X" * 1100
        + '<a href="/tenders/novyy-dizayn-sayta-detskih-tovarov-19012/">Source</a>'
        + '<a href="/tenders/novyy-dizayn-sayta-detskih-tovarov-19012/">Repeat</a>'
        + '<a href="https://evil.example/tenders/not-owned-19014/">Wrong domain</a>'
        + '<a href="/tenders/different-19013/?ref=tracking">Query link</a>'
        + '<a href="/tenders/one-extra-19022/">Another</a>'
        + "</html>"
    ).encode()
    assert discover_exact_cards(body, index_url=index) == [
        ("19012", "novyy-dizayn-sayta-detskih-tovarov", ORIGINAL),
        ("19022", "one-extra", "https://workspace.ru/tenders/one-extra-19022/"),
    ]
    with pytest.raises(ValueError):
        discover_exact_cards(body, index_url="https://evil.example/tenders/")


@pytest.mark.parametrize("url", [
    "http://workspace.ru/tenders/example-19012/",
    "https://workspace.ru/tenders/example-19012/?secret=yes",
    "https://workspace.ru@evil.example/tenders/example-19012/",
    "https://workspace.ru:443/tenders/example-19012/",
    "https://workspace.ru/tenders/example-19012/#target",
    "https://workspace.ru/tenders/example-19012/",
])
def test_url_rule_distinguishes_only_canonical_originals(url):
    if url == "https://workspace.ru/tenders/example-19012/":
        assert _canonical_card(url) == ("19012", "example")
    else:
        assert _canonical_card(url) is None


def test_llc_public_corporate_original_qualifies_only_as_candidate():
    row = _evaluate(_html())
    assert row["public_source_state"] == "PUBLIC_CANDIDATE_ONLY"
    assert row["printed_deadline_day"] == "2026-10-19"
    assert row["scope_attestation_state"] == "PRIORITY_ORIGINAL_REQUIREMENTS_ATTESTED"
    assert row["organizer_type"] == "Юридическое лицо"
    assert row["company_bidding_ready"] is False
    assert row["company_paid_or_free_reply_access_verified"] is False
    assert row["company_mandatory_portfolio_verified"] is False
    assert row["verified_legal_buyer_inn"] is False
    assert row["company_owner_go"] is False
    assert row["messages_or_payment_executed"] == 0
    assert len(row["source_sha256"]) == 64


@pytest.mark.parametrize(("opts", "state"), [
    ({"status": "Завершен"}, "CLOSED"),
    ({"status": "Отменен"}, "CLOSED"),
    ({"due": "17 октября 2026"}, "CLOSED"),
    ({"buyer": "Частное лицо"}, "REVIEW_REQUIRED"),
    ({"visibility": "private"}, "REVIEW_REQUIRED"),
    ({"original_requirements": False}, "REVIEW_REQUIRED"),
])
def test_noncorporate_closed_private_changed_requirements_fail_closed(opts, state):
    result = _evaluate(_html(**opts))
    assert result["public_source_state"] == state
    assert result["company_bidding_ready"] is False
    if "original_requirements" in opts:
        assert result["scope_attestation_state"] == "MANDATORY_PRIORITY_SOURCE_TEXT_MISSING"


@pytest.mark.parametrize("broken", [
    _html().replace(b"O\xd1\x80\xd0\xb3", b"ORG"),
    _html().replace(b"19 \xd0\xbe\xd0\xba\xd1\x82", b"unknown"),
    _html().replace(b"tendercart-type__status-public", b"tampered-status"),
    _html().replace(b"<h1>", b"<p>"),
])
def test_original_changed_layout_not_promoted_to_public_candidate(broken):
    with pytest.raises(ValueError):
        _evaluate(broken)


def test_synthetic_source_url_identity_tamper_rejected():
    with pytest.raises(ValueError):
        _evaluate(_html(), url="https://workspace.ru/tenders/other-19013/")


def test_saved_actual_three_indexes_31_origins_dedup_and_urgent_priority():
    assert SNAPSHOT["schema_version"] == "ta-b2b-workspace-first-party-three-it-categories-2026-10-18-v1"
    assert SNAPSHOT["unique_original_cards_checked"] == 31
    assert len({r["id"] for r in SNAPSHOT["rows"]}) == 31
    assert SNAPSHOT["original_public_corporate_accepting_candidates"] == 10
    assert SNAPSHOT["actual_company_eligible_to_respond_count"] == 0
    assert SNAPSHOT["legal_buyer_inn_confirmed_count"] == 0
    assert SNAPSHOT["actual_eligible_15_to_20_target_met"] is False
    assert SNAPSHOT["external_messages_or_purchases"] == 0
    assert len(SNAPSHOT["original_category_pages"]) == 3
    status = {r["id"]: r for r in SNAPSHOT["rows"]}
    assert status["19012"]["printed_deadline_day"] == "2026-10-19"
    assert status["19032"]["printed_deadline_day"] == "2026-10-21"
    assert status["19034"]["scope_attestation_state"] == "PRIORITY_ORIGINAL_REQUIREMENTS_ATTESTED"
    assert status["18939"]["scope_attestation_state"] == "PRIORITY_ORIGINAL_REQUIREMENTS_ATTESTED"
    assert status["19052"]["public_source_state"] == "REVIEW_REQUIRED"
    assert status["19003"]["public_source_state"] == "CLOSED"
    assert status["19023"]["public_source_state"] == "CLOSED"
    assert all(not r["company_bidding_ready"] for r in SNAPSHOT["rows"])
    assert all(r["messages_or_payment_executed"] == 0 for r in SNAPSHOT["rows"])
    for row in SNAPSHOT["rows"]:
        if row["public_source_state"] == "PUBLIC_CANDIDATE_ONLY":
            assert len(row["source_sha256"]) == 64
            assert row["source_http_status"] == 200
            assert row["organizer_type"] == "Юридическое лицо"
            assert row["visibility"] == "public"
