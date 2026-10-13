"""Source originality and conflicting deadlines must not become approved corporate bids."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.tender_research.corporate_lead_gate import triage_corporate_card

DATA = json.loads((
    Path(__file__).resolve().parents[1]
    / "docs/roadmap/b2b_source_live_addendum_2026-10-13.json"
).read_text(encoding="utf-8"))


def test_new_workspace_19023_original_receipt_is_not_a_bid_ready_claim():
    assert DATA["previous_historical_source_attested_count"] == 10
    assert DATA["added_unique_original_cards"] == 1
    assert DATA["distinct_historical_coverage_after_addendum"] == 11
    assert DATA["goal_met"] is False
    card = DATA["new_original_cards"][0]
    assert card["id"] == "workspace-19023"
    assert card["source_kind"] == "OFFICIAL_PUBLIC_PLATFORM_CARD"
    assert card["http_status"] == 200
    assert card["source_html_response_bytes"] > 20000
    assert len(card["source_html_sha256"]) == 64
    assert card["qualifying_past_aspro_cases"] == "NOT_CONFIRMED_FOR_ARVECTUM"
    assert card["application_deadline_time"] == "UNKNOWN"
    assert card["competitive_fit"] == "FIT_CONDITIONAL"
    observed_at = datetime.fromisoformat(card["checked_at"])
    result = triage_corporate_card({
        "source_url": card["source_url"],
        "organizer_type": card["organizer_type"],
        "platform_status": card["source_status"],
        "source_observed_at": card["checked_at"],
        "submission_deadline": card["application_deadline_date"],
    }, checked_at=observed_at)
    assert result.state == "PUBLIC_CANDIDATE_ONLY"
    assert result.bid_ready is False
    assert card["direct_bidding_or_registration_verified"] is False
    assert card["human_gold"] is False


def test_secondary_ink_deadline_disagreements_are_not_promoted_to_active():
    cases = DATA["conflicting_secondary_only"]
    assert len(cases) == 2
    assert {x["tender_id"] for x in cases} == {"INK-SZ-356-26", "INK-SZ-371-26"}
    for case in cases:
        assert not case["original_platform_notice_verified"]
        assert len(set(case["observed_deadline_dates"])) > 1
        assert case["result_state"] == "REVIEW_REQUIRED"
        assert case["bid_ready"] is False
        for url in case["secondary_urls"]:
            decision = triage_corporate_card({
                "source_url": url,
                "organizer_type": "Юридическое лицо",
                "platform_status": "Идет прием заявок",
                "source_observed_at": "2026-10-13T22:30:24+03:00",
                "submission_deadline": max(case["observed_deadline_dates"]),
            }, checked_at=datetime.fromisoformat("2026-10-13T22:30:24+03:00"))
            assert decision.state == "REVIEW_REQUIRED"
            assert decision.reason == "unsupported_original_platform_url"
            assert decision.bid_ready is False


def test_commercial_price_monitoring_and_marketing_are_not_it_development_awards():
    for item in DATA["not_admitted_other_cards"]:
        assert item["reason"]
        assert item["id"] in {"Fabrikant-3502252", "Workspace-19020"}
    assert DATA["fully_qualified_current_opportunities_claimed"] is None
    assert DATA["privacy_and_authority"]["no_registration"] is True
    assert DATA["privacy_and_authority"]["no_submission"] is True
    assert DATA["privacy_and_authority"]["legal_entity_eligibility_verified"] is False
