"""No real external bidding: proof-only original WordPress requirements checks."""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.acceptance.audit_workspace_19032_wordpress import (
    OTHER_REQUIRED,
    SCOPE_ANCHORS,
    evaluate_original,
)

ROOT = Path(__file__).resolve().parents[1] / "docs" / "roadmap"
PROOF = json.loads((ROOT / "b2b_workspace_19032_wordpress_source_2026-10-17.json").read_text())
NOW = datetime(2026, 10, 17, 19, 14, tzinfo=UTC)


def source(*, status="Идет прием заявок", deadline="21 октября 2026", remove=None):
    scope = " ".join([*OTHER_REQUIRED, *(part for values in SCOPE_ANCHORS.values() for part in values)])
    if remove:
        scope = scope.replace(remove, "")
    return (
        '<html><h1>Тех.обслуживание и доработка корпоративного сайта</h1>'
        f'<div class="tendercart-type__status-public">{status}</div>'
        '<div class="reference _public"></div>'
        'Oрганизатор <span>Юридическое лицо</span>'
        f'Крайний срок приема заявок: <span>{deadline}</span>'
        f'<article>{scope}</article></html>'
    ).encode()


def test_first_party_supported_parts_and_quote_questions_are_all_evidenced():
    x = evaluate_original(source(), observed_at=NOW)
    assert x["source_scope_anchor_counts"] == {
        "recurring_maintenance": 10,
        "separately_ordered_changes": 6,
        "requested_quote_fields": 6,
        "additional_questions": 1,
    }
    assert x["original_html_sha256"] == hashlib.sha256(source()).hexdigest()
    assert x["source_deadline_time"] == "UNKNOWN"
    assert x["budget_is_monthly_recurring_fee"] == "UNKNOWN"
    assert x["company_eligibility_state"] == "LLC_REVIEW_REQUIRED"
    assert all(value is None for value in x["draft_quote_not_yet_authorized"].values())
    assert (x["owner_bid_go"], x["external_messages_sent"], x["paid_actions"], x["signed_bids"]) == (False, 0, 0, 0)


@pytest.mark.parametrize("missing", [
    SCOPE_ANCHORS["recurring_maintenance"][3],
    SCOPE_ANCHORS["recurring_maintenance"][8],
    SCOPE_ANCHORS["separately_ordered_changes"][3],
    SCOPE_ANCHORS["requested_quote_fields"][2],
    SCOPE_ANCHORS["requested_quote_fields"][4],
    SCOPE_ANCHORS["additional_questions"][0],
    OTHER_REQUIRED[1],
    OTHER_REQUIRED[2],
])
def test_mandatory_missing_public_terms_fail_closed(missing):
    with pytest.raises(ValueError, match="missing first-party"):
        evaluate_original(source(remove=missing), observed_at=NOW)


def test_changed_source_budget_does_not_use_old_economic_assumptions():
    with pytest.raises(ValueError, match="budget|missing first-party"):
        evaluate_original(source(remove="100 000 - 400 000 рублей"), observed_at=NOW)


@pytest.mark.parametrize("status,deadline", [
    ("Прием заявок завершен", "21 октября 2026"),
    ("Идет прием заявок", "20 октября 2026"),
])
def test_changed_status_or_deadline_fail_closed(status, deadline):
    with pytest.raises(ValueError):
        evaluate_original(source(status=status, deadline=deadline), observed_at=NOW)


def test_naive_observation_time_is_not_trusted():
    with pytest.raises(ValueError, match="timezone"):
        evaluate_original(source(), observed_at=NOW.replace(tzinfo=None))


def test_pinned_real_first_party_source_evidence_does_not_claim_bid_readiness():
    assert PROOF["schema_version"] == "ta-b2b-wordpress-original-19032-v1"
    assert PROOF["procurement_card_id"] == "19032"
    assert PROOF["source_url"].startswith("https://workspace.ru/tenders/")
    assert PROOF["original_http_status"] == 200
    assert len(PROOF["original_html_sha256"]) == 64
    assert PROOF["source_scope_anchor_counts"] == {
        "recurring_maintenance": 10,
        "separately_ordered_changes": 6,
        "requested_quote_fields": 6,
        "additional_questions": 1,
    }
    assert PROOF["source_budget_rub_low"] == 100000
    assert PROOF["source_budget_rub_high"] == 400000
    assert PROOF["source_deadline_time"] == "UNKNOWN"
    assert PROOF["budget_is_monthly_recurring_fee"] == "UNKNOWN"
    assert PROOF["public_page_requests_agency_or_specialist_login"] is True
    assert PROOF["current_company_reply_entitlement_verified"] is False
    assert PROOF["company_wordpress_commercial_references_verified"] is False
    assert PROOF["company_eligibility_state"] == "LLC_REVIEW_REQUIRED"
    assert all(x is None for x in PROOF["draft_quote_not_yet_authorized"].values())
    assert PROOF["owner_bid_go"] is False
