"""Fail-closed LLC gate and reproducibility on first-party 17 Oct evidence."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.b2b_llc_eligibility_snapshot import build_snapshot
from src.tender_research.corporate_lead_gate import qualify_llc_response

NOW = datetime(2026, 10, 17, 21, 22, tzinfo=timezone(timedelta(hours=3)))
CARD = {
    "source_url": "https://workspace.ru/tenders/sait-19032/",
    "organizer_type": "Юридическое лицо",
    "platform_status": "Идет прием заявок",
    "source_observed_at": "2026-10-17T17:19:58+03:00",
    "submission_deadline": "2026-10-21",
}
SHA = "a" * 64


def screen(**overrides):
    return qualify_llc_response(
        overrides.pop("card", CARD),
        checked_at=overrides.pop("checked_at", NOW),
        source_sha256=overrides.pop("source_sha256", SHA),
        source_http_status=overrides.pop("source_http_status", 200),
        **overrides,
    )


def test_open_original_source_is_never_llc_authorization():
    r = screen()
    assert r.state == "LLC_REVIEW_REQUIRED"
    assert r.response_authorized is False
    assert "company_reply_channel_unverified" in r.blockers
    assert "company_legal_eligibility_unverified" in r.blockers


def test_terminal_source_overrules_all_positive_flags():
    r = screen(card={**CARD, "platform_status": "Завершён"},
               company_legal_eligibility_verified=True,
               mandatory_qualification_verified=True,
               company_reply_channel_verified=True, commercial_terms_approved=True)
    assert r.state == "CLOSED"
    assert r.response_authorized is False


def test_stale_card_does_not_become_eligible_from_owner_flags():
    r = screen(checked_at=NOW + timedelta(days=3),
               company_legal_eligibility_verified=True,
               mandatory_qualification_verified=True,
               company_reply_channel_verified=True, commercial_terms_approved=True)
    assert r.state == "SOURCE_REVIEW_REQUIRED"
    assert r.response_authorized is False


def test_original_receipt_required_even_for_public_open_card():
    assert "original_source_integrity_unverified" in screen(source_sha256="missing").blockers
    assert "original_source_integrity_unverified" in screen(source_http_status=403).blockers


def test_all_positive_flags_still_require_human_go():
    r = screen(company_legal_eligibility_verified=True,
               mandatory_qualification_verified=True,
               company_reply_channel_verified=True, commercial_terms_approved=True)
    assert r.state == "HUMAN_GO_REQUIRED"
    assert r.response_authorized is False


def test_actual_source_bound_five_originals_are_not_company_bid_ready():
    actual = build_snapshot(NOW)
    assert actual == build_snapshot(NOW)
    assert actual["original_case_count"] == 5
    assert actual["company_qualified_to_respond_count"] == 0
    assert actual["actual_replies_or_paid_actions"] == 0
    assert [x["id"] for x in actual["cases"]] == ["19032", "19042", "19043", "19006", "19030"]
    assert all(x["eligibility_state"] == "LLC_REVIEW_REQUIRED" for x in actual["cases"])
    assert all(x["response_authorized"] is False for x in actual["cases"])
    assert all(len(x["source_html_sha256"]) == 64 for x in actual["cases"])



def test_checked_in_snapshot_is_reproducible():
    path = Path(__file__).resolve().parents[1] / "docs/roadmap/b2b_llc_eligibility_snapshot_2026-10-17.json"
    assert json.loads(path.read_text(encoding="utf-8")) == build_snapshot(NOW)
