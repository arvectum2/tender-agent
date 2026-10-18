"""Literal official policy rules are not real Arvectum LLC bidder admission."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.acceptance import audit_b2b_llc_platform_rules_20261018 as gate

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = json.loads(
    (ROOT / "docs/roadmap/b2b_llc_first_party_platform_policy_2026-10-18.json")
    .read_text(encoding="utf-8")
)
NOW = datetime(2026, 10, 18, 11, 5, tzinfo=UTC)


def _html_page(name: str, *, remove: str | None = None) -> bytes:
    anchors = list(gate.PROOFS[name])
    if remove:
        anchors.remove(remove)
    return (
        "<html><body><article>" + " ".join(anchors)
        + "</article>" + " First party legal text. " * 110
        + "</body></html>"
    ).encode("utf-8")


def test_all_nine_original_urls_are_exact_allowlisted_and_source_bounded():
    assert len(gate.ORIGINALS) == 9
    assert set(gate.ORIGINALS) == set(gate.PROOFS)
    assert gate.ORIGINALS["workspace_terms"].endswith("/terms_of_use.pdf")
    assert gate.ORIGINALS["codelance_signup"].endswith("/site/signup")
    for name, url in gate.ORIGINALS.items():
        assert url.startswith("https://")
        assert len(gate.PROOFS[name]) >= 3
    assert gate.PDF_MAX < 1_000_000
    assert gate.HTML_MAX < 1_000_000


@pytest.mark.parametrize("name", [k for k in gate.ORIGINALS if k != "workspace_terms"])
def test_exact_first_party_html_proofs_validate_but_not_company_account(name):
    row = gate.verify_original_policy(name, _html_page(name))
    assert row["source"] == name
    assert row["exact_url"] == gate.ORIGINALS[name]
    assert row["original_status_http"] == 200
    assert row["is_authenticated_company_session"] is False
    assert row["original_clause_fragments"] == list(gate.PROOFS[name])
    assert len(row["html_or_pdf_sha256"]) == 64


@pytest.mark.parametrize("name", [k for k in gate.ORIGINALS if k != "workspace_terms"])
def test_missing_original_policy_clause_is_fail_closed(name):
    for fragment in gate.PROOFS[name]:
        with pytest.raises(ValueError, match="changed or missing anchor"):
            gate.verify_original_policy(name, _html_page(name, remove=fragment))


def test_workspace_latest_pdf_edition_must_not_reuse_stale_2024_snapshot(monkeypatch):
    assert "Редакция от 06.07.2026 г." in gate.PROOFS["workspace_terms"]
    assert "уполномоченным сотрудником юридического лица" in gate.PROOFS["workspace_terms"]
    good = gate._normalized(" ".join(gate.PROOFS["workspace_terms"]))
    monkeypatch.setattr(gate, "_policy_text", lambda name, raw: good)
    sample = b"%PDF-1.7\n" + b"X" * 2400
    gate.verify_original_policy("workspace_terms", sample)
    stale = good.replace("06.07.2026", "10.09.2024")
    monkeypatch.setattr(gate, "_policy_text", lambda name, raw: stale)
    with pytest.raises(ValueError, match="changed or missing anchor"):
        gate.verify_original_policy("workspace_terms", sample)


def test_invalid_pdf_and_unknown_source_not_silently_accepted():
    with pytest.raises(ValueError):
        gate.verify_original_policy("workspace_terms", b"<html/>" * 450)
    with pytest.raises(ValueError):
        gate.verify_original_policy("untrusted_doc", b"x" * 3000)
    with pytest.raises(ValueError, match="unapproved first-party"):
        gate._source_get("https://evil.example/legal")
    with pytest.raises(ValueError, match="unapproved first-party"):
        gate._source_get("https://workspace.ru/login/?user=company")


def test_provider_general_policy_does_not_claim_an_arvectum_signed_bid(monkeypatch):
    rows = {k: b"source" * 500 for k in gate.ORIGINALS}
    monkeypatch.setattr(
        gate, "verify_original_policy",
        lambda name, raw: {
            "source": name, "exact_url": gate.ORIGINALS[name],
            "is_authenticated_company_session": False,
        },
    )
    result = gate.qualify_provider(rows, observed=NOW)
    assert result["first_party_policies_checked"] == 9
    assert result["workspace"]["legal_entity_as_agency_explicit_in_agreement"] is True
    assert result["workspace"]["invited_agency_reply_free_by_official_faq"] is True
    assert result["workspace"]["default_self_initiated_tender_reply_requires_pro"] is True
    assert result["workspace"]["actual_llc_agency_profile_authenticated"] is False
    assert result["workspace"]["specific_tender_invitation_verified"] is False
    assert result["contractis"]["published_start_free_replies_per_month"] == 5
    assert result["contractis"]["five_test_replies_are_conditional_not_automatic"] is True
    assert result["contractis"]["explicit_verified_llc_registration_mode"] is False
    assert result["contractis"]["customer_performer_contract_direct"] is True
    assert result["codelance"]["public_free_developer_replies"] is True
    assert result["codelance"]["explicit_verified_llc_registration_mode"] is False
    assert result["codelance"]["subsequent_corporate_profile_options_inspected"] is False
    assert result["current_arvectum_llc_bid_authority_across_all_three"] == 0
    assert result["registrations_bids_payments_emails_signatures_executed"] == 0
    assert result["new_distinct_b2b_it_procurement_opportunities"] == 0
    with pytest.raises(ValueError, match="incomplete"):
        gate.qualify_provider({k: v for k, v in rows.items() if k != "codelance_signup"}, observed=NOW)


def test_saved_official_receipt_pins_policy_without_company_access():
    r = RECEIPT
    assert r["schema_version"] == "ta-b2b-first-party-llc-platform-policy-2026-10-18-v1"
    assert r["first_party_policies_checked"] == 9
    assert {row["source"] for row in r["source_documents"]} == set(gate.ORIGINALS)
    assert r["workspace"]["legal_entity_as_agency_explicit_in_agreement"] is True
    assert r["workspace"]["legal_agent_must_be_authorized_representative"] is True
    assert r["workspace"]["default_self_initiated_tender_reply_requires_pro"] is True
    assert r["workspace"]["invited_agency_reply_free_by_official_faq"] is True
    assert r["workspace"]["published_company_invoice_payment_option"] is True
    assert r["workspace"]["actual_llc_agency_profile_authenticated"] is False
    assert r["contractis"]["public_pro_month_rub"] == 499
    assert r["contractis"]["public_pro_quarter_rub"] == 999
    assert r["contractis"]["published_start_free_replies_per_month"] == 5
    assert r["contractis"]["five_test_replies_are_conditional_not_automatic"] is True
    assert r["contractis"]["specific_company_account_free_reply_quota_verified"] is False
    assert r["codelance"]["separate_legal_entity_fields_verified_in_first_form"] is False
    assert r["codelance"]["explicit_verified_llc_registration_mode"] is False
    assert r["codelance"]["actual_company_contract_and_payout_verified"] is False
    assert r["current_arvectum_llc_bid_authority_across_all_three"] == 0
    assert r["registrations_bids_payments_emails_signatures_executed"] == 0
    assert r["new_distinct_b2b_it_procurement_opportunities"] == 0
    assert all(len(row["html_or_pdf_sha256"]) == 64 for row in r["source_documents"])
    assert all(row["is_authenticated_company_session"] is False for row in r["source_documents"])
    assert "\"password\":" not in json.dumps(r)
    assert "access_token" not in json.dumps(r)
    assert "/Volumes/ArvectumSSD" not in json.dumps(r)
