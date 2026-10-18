"""Unregistered browser listing evidence: public quote != company IT eligibility."""
from __future__ import annotations

import json
from pathlib import Path

REPORT = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "docs/roadmap/b2g_moscow_public_registry_browser_2026-10-18.json"
    ).read_text(encoding="utf-8")
)


def test_public_registry_navigation_is_source_specific_but_not_qualified_lot():
    assert REPORT["schema_version"] == (
        "ta-b2g-moscow-browser-public-registry-navigation-2026-10-18-v1"
    )
    assert REPORT["source"] == "https://zakupki.mos.ru/"
    assert REPORT["first_party_public_navigation_label"] == "Реестр котировочных сессий"
    assert REPORT["browser_mode"] == "HEADLESS_CHROME_DISPOSABLE_UNAUTHENTICATED"
    assert REPORT["browser_disposable_profile_location"] == "ARVECTUM_SSD_TMP_NO_USER_PROFILE"
    assert REPORT["public_registry_opened"] is True
    assert REPORT["public_registry_route"] == "/purchase/list"
    assert REPORT["original_numbered_quote_list_visible"] is True
    assert REPORT["numbered_current_it_quote_original_detail_cards_verified"] == 0
    assert REPORT["full_it_quote_documentation_downloaded"] is False


def test_real_non_it_list_example_rejected_instead_of_b2b_bid():
    example = REPORT["quote_list_item_example"]
    assert example["public_list_id"] == "10321388"
    assert example["public_list_status"] == "АКТИВНАЯ"
    assert example["public_list_subject"] == "РАСТВОРИТЕЛИ (РАЗБАВИТЕЛИ)"
    assert example["buyer_inn"] == "7709010548"
    assert example["published_initial_amount_rub"] == "44700.00"
    assert example["published_submission_end_msk"] == "2026-10-20T10:00:00"
    assert example["law"] == "223-ФЗ"
    assert example["is_it_procurement"] is False
    assert example["original_detail_card_inspected"] is False
    assert example["should_enter_arvectum_it_qualified_leads"] is False


def test_company_auth_ukep_go_and_send_never_inferred_from_public_registry():
    assert REPORT["company_account_authenticated"] is False
    assert REPORT["company_ukep_attached_verified"] is False
    assert REPORT["company_authorized_bidding_access_verified"] is False
    assert REPORT["company_owner_go"] is False
    assert REPORT["b2b_corporate_lead_target_increment"] == 0
    assert REPORT["outgoing_communications_signatures_or_paid_actions"] == 0
    assert REPORT["browser_profile_persisted"] is False
    exported = json.dumps(REPORT)
    for secret in ("password", "secret_key", "access_token", "/Volumes/ArvectumSSD"):
        assert secret not in exported


def test_read_only_browser_script_no_send_bid_or_submit():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts/acceptance/audit_moscow_public_registry_navigation_20261018.mjs"
    ).read_text()
    assert "https://zakupki.mos.ru/" in script
    assert "Реестр котировочных сессий" in script
    assert "mkdtemp" in script
    assert "await rm(profile" in script
    assert "new WebSocket(" in script
    assert "connection.send(JSON.stringify({id,method,params}))" in script
    assert "verified_current_it_bids:0" in script
    assert "sent_reply:false" in script
    assert "fetch('https://zakupki.mos.ru/api" not in script
    assert "submitBid" not in script
    assert "registerCompany" not in script
