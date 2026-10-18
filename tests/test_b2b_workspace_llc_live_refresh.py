"""Original-only source refresh must never imply company bid or payment permission."""
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.acceptance.refresh_workspace_llc_originals import (
    evaluate_original,
    original_cases,
)

ROOT = Path(__file__).resolve().parents[1] / "docs" / "roadmap"
REPORT = json.loads((ROOT / "b2b_workspace_llc_live_recheck_2026-10-17.json").read_text())
CASE = next(x for x in original_cases() if x["id"] == "19032")
WHEN = datetime(2026, 10, 17, 19, 2, tzinfo=UTC)


def document(*, status="Идет прием заявок", due="21 октября 2026", missing=False):
    anchors = "" if missing else " ".join(CASE["anchors"])
    return (f'<html><h1>WordPress corporate service</h1>'
            f'<div class="tendercart-type__status-public">{status}</div>'
            '<div class="reference _public"></div>'
            'Oрганизатор <span>Юридическое лицо</span>'
            f'Крайний срок приема заявок: <span>{due}</span>'
            f'<article>{anchors}</article></html>').encode()


def test_original_five_are_bounded_exact_card_urls():
    cards = original_cases()
    assert [c["id"] for c in cards] == ["19032", "19042", "19043", "19006", "19030"]
    assert len({c["url"] for c in cards}) == 5
    assert all(re.fullmatch(r"[a-f0-9]{64}", c["old_sha"]) for c in cards)
    assert all(c["anchors"] for c in cards)


def test_original_public_card_still_never_authorizes_llc_response():
    r = evaluate_original(CASE, document(), observed=WHEN)
    assert r["source_status"] == "PUBLIC_CANDIDATE_ONLY"
    assert r["mandatory_text_anchors_verified"] is True
    assert r["company_response_eligibility"] == "LLC_REVIEW_REQUIRED"
    assert r["response_authorized"] is False
    assert r["owner_go"] is False
    assert "company_reply_channel_unverified" in r["unresolved_llc_gates"]


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (document(status="Завершён"), "original_source_changed_or_ambiguous"),
        (document(due="22 октября 2026"), "original_source_changed_or_ambiguous"),
        (document(missing=True), "original_requirement_anchors_missing"),
        (b"not html", "original_source_changed_or_ambiguous"),
    ],
)
def test_changed_or_incomplete_original_never_promotes_to_live_or_bid_ready(body, reason):
    r = evaluate_original(CASE, body, observed=WHEN)
    assert r["source_status"] == "SOURCE_REVIEW_REQUIRED"
    assert r["source_reason"] == reason
    assert r["response_authorized"] is False
    assert r["company_response_eligibility"] == "NOT_VERIFIED"


def test_live_receipt_preserves_real_original_sources_and_explicit_unknowns():
    assert REPORT["schema_version"] == "workspace-first-party-llc-refresh-v1"
    assert REPORT["original_card_count"] == 5
    assert REPORT["public_candidate_count"] == 5
    assert REPORT["confirmed_llc_response_eligibility_count"] == 0
    assert REPORT["externally_submitted_replies_or_paid_actions"] == 0
    assert REPORT["source_hash_change_is_not_proof_of_material_notice_change"] is True
    expected = {x["id"]: x for x in original_cases()}
    for x in REPORT["cases"]:
        assert x["source_url"] == expected[x["id"]]["url"]
        assert x["source_http_status"] == 200
        assert len(x["original_html_sha256"]) == 64
        assert x["mandatory_text_anchors_verified"] is True
        assert x["source_status"] == "PUBLIC_CANDIDATE_ONLY"
        assert x["company_response_eligibility"] == "LLC_REVIEW_REQUIRED"
        assert x["paid_actions_or_responses"] == 0
        assert x["owner_go"] is False
        assert x["response_authorized"] is False
        assert datetime.fromisoformat(x["source_observed_at_utc"]).tzinfo is not None
        assert x["published_deadline_date"] == expected[x["id"]]["deadline"]
        assert x["deadline_clock_time"] == "UNKNOWN"


def test_stored_live_receipt_does_not_promote_public_observations_to_owner_go():
    assert not any(x["response_authorized"] or x["owner_go"] for x in REPORT["cases"])
    assert all(
        "company_legal_eligibility_unverified" in x["unresolved_llc_gates"]
        for x in REPORT["cases"]
    )
