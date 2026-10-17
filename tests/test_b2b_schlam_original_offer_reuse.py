"""Existing Arvectum /schlam demo source QA must never authorize a bid."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from scripts.acceptance.audit_schlam_offer_original_oct17 import _Markup

ROOT = Path(__file__).resolve().parents[1] / "docs/roadmap"
R = json.loads((ROOT / "b2b_schlam_19006_original_offer_qa_2026-10-17.json").read_text())


def test_first_party_workspace_exact_original_card_is_company_public_snapshot_not_go():
    assert R["schema_version"] == "ta-schlam-original-19006-reuse-qa-v1"
    assert datetime.fromisoformat(R["checked_at_utc"]).tzinfo is not None
    source = R["original_workspace_card"]
    assert source["url"] == (
        "https://workspace.ru/tenders/"
        "sozdanie-i-dalneyshee-razvitie-sayta-specializirovannoy-kompanii-"
        "po-rabotam-na-vode-i-trudnodostupnyh-obektah-19006/"
    )
    assert re.fullmatch("[a-f0-9]{64}", source["original_html_sha256"])
    assert source["original_html_bytes"] > 30_000
    assert source["status"] == "Идет прием заявок"
    assert source["organizer_type"] == "Юридическое лицо"
    assert source["deadline_date"] == "2026-11-01"
    assert source["deadline_clock"] == "UNKNOWN"
    assert source["source_budget_min_rub"] == 130_000
    assert source["source_budget_max_rub"] == 400_000
    assert "Подробное техническое задание намеренно пока не формируем." in (
        source["original_literal_source_requirements"]
    )
    assert not R["company_paid_workspace_access_or_invitation_verified"]
    assert not R["bid_ready"] and not R["human_go"]


def test_exact_six_preexisting_demo_pages_are_not_indexed_and_not_new_ui():
    urls = [x["url"] for x in R["published_demo_pages"]]
    assert urls == [
        "https://arvectum.com/schlam/",
        "https://arvectum.com/schlam/market/",
        "https://arvectum.com/schlam/offer/",
        "https://arvectum.com/schlam/brief/",
        "https://arvectum.com/schlam/equipment/",
        "https://arvectum.com/schlam/crm/",
    ]
    assert R["site_repo_known"] == "arvectum2/arvectum-site"
    assert R["no_new_site_ui_or_external_action"] is True
    for page in R["published_demo_pages"]:
        assert page["robots_noindex"] is True
        assert page["http_status"] == 200
        assert page["existing_site_unchanged"] is True
        assert page["size"] > 1000
        assert re.fullmatch("[a-f0-9]{64}", page["html_sha256"])


def test_original_existing_internal_links_are_bounded_readonly_and_healthy():
    records = R["internal_link_checks"]
    assert len(records) >= 20
    assert len({x["url"] for x in records}) == len(records)
    for link in records:
        assert link["url"].startswith("https://arvectum.com/schlam/")
        assert "?" not in link["url"]
        assert link["http_status"] == 200
        assert link["bytes"] > 0


def test_existing_low_entrance_price_is_not_profit_or_complete_full_contract():
    budget = R["original_workspace_card"]
    assert R["existing_offer_start_price_rub"] == 89_000
    assert R["existing_offer_start_price_rub"] < budget["source_budget_min_rub"]
    assert R["existing_offer_estimate_weeks"] == "4–6"
    assert R["existing_offer_below_public_budget_min_not_auto_bad_but_owner_cost_gate"] is True
    assert R["published_demo_not_real_customer_technical_facts"] is True
    assert R["human_go"] is False


def test_original_report_does_not_fake_niche_research_or_submission():
    report = (ROOT / "B2B_SCHLAM_19006_OFFER_REUSE_QA_2026-10-17.md").read_text()
    assert "7 сайтов" in report
    assert "8 кластеров" in report
    assert "Wordstat" in report
    assert "89 000 ₽" in report
    assert "130 000" in report
    assert "noindex" in report
    assert "не подтверждены" in report
    assert "COMPANY_BID_READY=false" in report


def test_markup_parser_keeps_noindex_separate_from_bogus_inline_claim():
    p = _Markup()
    p.feed("<html><head><meta name='robots' content='index,follow'></head>"
           "<body><p>noindex in content only</p><a href='/schlam/'>go</a></body></html>")
    assert p.robots == ["index,follow"]
    assert "noindex" in p.text
    assert p.urls == ["/schlam/"]
