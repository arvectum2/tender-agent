"""B2G supplier route must not inflate LLC-ready B2B opportunities."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.acceptance.audit_moscow_supplier_entry_20261018 import (
    OFFICIAL_PAGES,
    REVIEWED_POLICY_CLAUSES,
    audit_official_sources,
    audit_policy_page,
    audit_portal_spa_shell,
)

REPORT = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "docs/roadmap/b2g_moscow_supplier_first_party_policy_2026-10-18.json"
    ).read_text(encoding="utf-8")
)


def _policy_body(name: str, *, omit: str | None = None) -> bytes:
    fragments = list(REVIEWED_POLICY_CLAUSES[name])
    if omit is not None:
        fragments.remove(omit)
    return (
        "<html><body>" + "official public regulator policy " * 90
        + " ".join(fragments)
        + "</body></html>"
    ).encode("utf-8")


def _spa_shell() -> bytes:
    return (
        "<html><head></head><body><noscript>"
        "You need to enable JavaScript to run this app."
        "</noscript>"
        '<script src="/lib/cadesplugin_api.js?17920"></script>'
        + "script " * 490
        + "</body></html>"
    ).encode("utf-8")


def test_official_original_regulator_policy_is_source_bound():
    assert len(REVIEWED_POLICY_CLAUSES) == 4
    assert len(OFFICIAL_PAGES) == 5
    for name in REVIEWED_POLICY_CLAUSES:
        result = audit_policy_page(name, _policy_body(name))
        assert result["exact_official_url"] == OFFICIAL_PAGES[name]
        assert result["original_http_status"] == 200
        assert result["company_session_authenticated"] is False
        assert len(result["original_html_sha256"]) == 64
        assert len(result["attested_clauses"]) == len(REVIEWED_POLICY_CLAUSES[name])
        assert all(
            c["source_evidence_state"] == "LITERAL_ORIGINAL_POLICY_ATTESTED"
            for c in result["attested_clauses"]
        )


@pytest.mark.parametrize("policy", list(REVIEWED_POLICY_CLAUSES))
def test_removing_any_required_official_policy_clause_fails_closed(policy):
    for phrase in REVIEWED_POLICY_CLAUSES[policy]:
        with pytest.raises(ValueError, match="missing or changed"):
            audit_policy_page(policy, _policy_body(policy, omit=phrase))


def test_public_javascript_app_shell_is_not_a_verified_live_quote_listing():
    result = audit_portal_spa_shell(_spa_shell())
    assert result["public_response_is_client_side_javascript_application"] is True
    assert result["live_quote_sessions_parsed_from_actual_original_cards"] == 0
    assert result["live_quote_session_cards_checked"] is False
    assert result["live_it_quote_session_eligibility_verified"] is False
    assert result["do_not_claim_no_real_it_auctions"] is True
    assert result["company_session_authenticated"] is False
    with pytest.raises(ValueError, match="layout no longer verified"):
        audit_portal_spa_shell(_spa_shell().replace(
            b"You need to enable JavaScript to run this app.",
            b"Now rendering actual auction cards",
        ))


def test_email_only_is_viewing_not_bidding_and_optional_training_not_fee():
    sample = {p: _policy_body(p) for p in REVIEWED_POLICY_CLAUSES}
    sample["supplier_portal_shell"] = _spa_shell()
    result = audit_official_sources(sample)
    assert result["free_initial_registration_claim_attested"] is True
    assert result["email_only_registration_authorizes_bidding"] is False
    assert result["electronic_signature_for_legally_binding_actions_required"] is True
    assert result["public_company_supplier_category_allowed"] is True
    assert result["company_full_supplier_registration_completed_verified"] is False
    assert result["company_ukep_current_portal_linkage_verified"] is False
    assert result["quoted_optional_training_rub"] == 7000
    assert result["quoted_optional_priority_support_one_month_from_rub"] == 10000
    assert result["optional_services_are_compulsory_auction_fees"] is False
    assert result["platform_auction_operational_duration_hours"] == [3, 6, 24]
    assert result["buyer_channel_category"] == "B2G_SMALL_PURCHASES_NOT_CORPORATE_B2B"
    assert result["verified_live_it_quote_session_count"] == 0
    assert result["verified_live_quote_session_search_performed"] is False
    assert result["no_new_qualified_corporate_b2b_leads"] is True
    assert result["company_authorized_bid_go"] is False
    assert result["registrations_money_signatures_or_bids_executed"] == 0


def test_missing_or_added_regulatory_source_fails_closed():
    pages = {p: _policy_body(p) for p in REVIEWED_POLICY_CLAUSES}
    pages["supplier_portal_shell"] = _spa_shell()
    for source in list(pages):
        with pytest.raises(ValueError, match="missing or extra"):
            audit_official_sources({k: v for k, v in pages.items() if k != source})
    with pytest.raises(ValueError, match="missing or extra"):
        audit_official_sources({**pages, "untrusted-domain": b"<html/>"})


def test_real_saved_receipt_zero_b2b_count_and_no_company_bid_authority():
    report = REPORT
    assert report["schema_version"] == "ta-b2g-moscow-portal-original-registration-policy-2026-10-18-v1"
    assert report["official_source_count"] == 5
    assert len(report["sources"]) == 5
    assert {row["policy_kind"] for row in report["sources"]} == set(OFFICIAL_PAGES)
    assert report["free_initial_registration_claim_attested"] is True
    assert report["email_only_registration_authorizes_bidding"] is False
    assert report["company_full_supplier_registration_completed_verified"] is False
    assert report["company_authorized_bid_go"] is False
    assert report["buyer_channel_category"] == "B2G_SMALL_PURCHASES_NOT_CORPORATE_B2B"
    assert report["verified_live_it_quote_session_count"] == 0
    assert report["no_new_qualified_corporate_b2b_leads"] is True
    assert report["registrations_money_signatures_or_bids_executed"] == 0
    assert all(len(row["original_html_sha256"]) == 64 for row in report["sources"])
    assert "user_password" not in json.dumps(report)
    assert "access_token" not in json.dumps(report)
    assert "/Volumes/ArvectumSSD" not in json.dumps(report)
