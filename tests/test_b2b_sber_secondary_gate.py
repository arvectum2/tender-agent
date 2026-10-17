"""Secondary tender leads must not be silently promoted to original live bids."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.tender_research.corporate_lead_gate import triage_corporate_card

DATA = json.loads((
    Path(__file__).resolve().parents[1]
    / "docs/roadmap/b2b_sber_zvuk_secondary_gate_2026-10-13.json"
).read_text(encoding="utf-8"))


def test_sber_original_host_reachable_is_not_original_tender_proof():
    original = DATA["first_party_site_check"]
    secondary = DATA["unverified_secondary_candidate"]
    assert original["http_status"] == 200
    assert original["url"] == "https://www.sberbank-ast.ru/"
    assert len(original["sha256"]) == 64
    assert not original["specific_tender_public_card_found"]
    assert not original["specific_tender_number_in_homepage_html"]
    assert secondary["id"] == "SBR028-2610130033"
    assert secondary["original_platform_notice_url"] is None
    assert not secondary["original_notice_verified"]
    assert not secondary["original_documents_verified"]
    assert secondary["source_status"] == "SECONDARY_ONLY_REVIEW_REQUIRED"
    assert secondary["bid_ready"] is False
    assert secondary["external_action_allowed"] is False


def test_kontur_aggregator_does_not_pass_original_corporate_card_gate():
    source = DATA["unverified_secondary_candidate"]
    observed_at = datetime.fromisoformat(DATA["audit_time_msk"])
    result = triage_corporate_card({
        "source_url": source["secondary_url"],
        "organizer_type": "Юридическое лицо",
        "platform_status": "Идет прием заявок",
        "submission_deadline": source["deadline_msk_claimed"],
        "source_observed_at": DATA["audit_time_msk"],
    }, checked_at=observed_at)
    assert result.state == "REVIEW_REQUIRED"
    assert result.reason == "unsupported_original_platform_url"
    assert result.bid_ready is False


def test_new_workspace_index_not_counted_as_verified_corporate_it_contracts():
    index = DATA["workspace_current_index"]
    assert index["http_status"] == 200
    assert len(index["sha256"]) == 64
    assert index["new_verified_corporate_it_cards_added"] == 0
    assert set(index["observed_ids"]) == {"19023", "19026", "19027"}
    reasons = {x["id"]: x["reason"] for x in index["new_index_cards_not_promoted"]}
    assert reasons["19026"] == "NON_SOFTWARE_MARKETPLACE_OPERATIONS"
    assert reasons["19027"] == "MIXED_COPYWRITING_DESIGN_ORGANIZER_ORIGINAL_UNCHECKED"


def test_current_qualified_opportunities_still_not_proven():
    status = DATA["coverage"]
    assert status["prior_distinct_historical_corporate_it_cards"] == 11
    assert status["distinct_historical_corporate_it_cards_after"] == 11
    assert status["new_first_party_contract_cards_verified"] == 0
    assert status["currently_qualified_opportunity_count"] is None
    assert status["goal_met"] is False
    assert DATA["constraints"]["no_original_platform_bypass"] is True
    assert DATA["constraints"]["no_bid_or_contact"] is True
