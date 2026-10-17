"""Source-bounded LLC App Store proof and Workspace mobile PRO/fit gates."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from scripts.acceptance.audit_workspace_mobile_appstore_20261017 import (
    _apple_original_facts,
    _card_original_facts,
)

ROOT = Path(__file__).resolve().parents[1] / "docs/roadmap"
D = json.loads((ROOT / "b2b_workspace_mobile_appstore_original_2026-10-17.json").read_text())


def test_original_workspace_mobile_pro_prices_not_generic_2900():
    assert D["schema_version"] == "arvectum-firstparty-apple-workspace-mobile-b2b-20261017-v1"
    assert D["workspace_official_pro_category_source"] == "https://workspace.ru/advertising/"
    assert D["workspace_app_development_product_code"] == "MOB"
    assert re.fullmatch("[a-f0-9]{64}", D["workspace_official_pro_html_sha256"])
    assert D["original_advertised_app_category_PRO_rub"] == {
        "1_month": 16900,
        "3_months": 45630,
        "6_months": 86190,
        "12_months": 152100,
    }
    assert D["original_advertised_app_PRO_1_month_rub"] == 16900
    assert D["generic_cheapest_content_category_not_app_price_rub"] == 2900
    assert D["original_advertised_app_PRO_1_month_rub"] > 2900
    assert datetime.fromisoformat(D["checked_at_utc"]).tzinfo is not None


@pytest.mark.parametrize(("app_id", "name", "version"), [
    (6818711298, "ChickMark: трекер привычек", "1.4.1"),
    (6816346084, "Фото и PDF под размер", "1.0.1"),
    (6816013574, "Arvectum Proxy Launcher", "0.1.37"),
])
def test_actual_llc_arvectum_first_party_apple_store_references(app_id, name, version):
    assert D["verified_llc_apple_published_product_count"] == 3
    app = next(a for a in D["verified_official_apple_company_portfolio"]
               if a["app_store_numeric_id"] == app_id)
    assert app["track_name"] == name
    assert app["app_store_link"] == f"https://apps.apple.com/ru/app/id{app_id}"
    assert app["first_party_recorded_seller"] == "LLC ARVECTUM"
    assert app["first_party_artist"] == "ARVECTUM"
    assert app["published_version_at_observation"] == version
    assert app["verified_official_apple_lookup_http200"] is True
    assert re.fullmatch("[a-f0-9]{64}", app["official_apple_lookup_raw_sha256"])
    assert not app["published_client_commissioning_proven"]
    assert not app["three_year_commercial_development_duration_proven"]
    assert not app["android_delivery_proven"]


@pytest.mark.parametrize(("seller", "name", "app_id"), [
    ("OTHER DEVELOPER", "ChickMark: трекер привычек", "6818711298"),
    ("LLC ARVECTUM", "ChickMark: трекер привычек", "1111111111"),
    ("LLC ARVECTUM", "Fictitious title", "6818711298"),
])
def test_apple_reference_requires_exact_official_seller_id_name(seller, name, app_id):
    blob = json.dumps({"resultCount": 1, "results": [{
        "trackId": int(app_id), "kind": "software",
        "sellerName": seller, "trackName": name,
        "trackViewUrl": f"https://apps.apple.com/ru/app/id{app_id}",
    }]}).encode()
    with pytest.raises(ValueError):
        _apple_original_facts(blob, "6818711298")


def test_public_mobile_cards_are_not_owner_bid_go():
    cases = {x["id"]: x for x in D["current_source_workspace_mobile_cards"]}
    assert len(cases) == 3
    assert D["current_public_corporate_mobile_candidates"] == 2
    assert D["excluded_personal_organizers"] == 1
    assert D["arvectum_mobile_bid_ready_count"] == 0
    assert D["verified_android_client_delivery_count"] == 0
    assert D["owner_pro_purchase_approved"] is False
    assert D["platform_authenticated_account_mobile_category_verified"] is False
    assert D["owner_company_eligibility_verified"] is False
    assert D["no_external_bids_registration_payment_or_new_ui"] is True
    for card in cases.values():
        assert card["platform_status"] == "Идет прием заявок"
        assert card["visibility"] == "public"
        assert card["source_http_status"] == 200
        assert re.fullmatch("[a-f0-9]{64}", card["original_source_html_sha256"])
        assert card["full_locked_tender_spec_inspected"] is False
        assert card["our_own_three_year_commercial_mobile_contract_history_proven"] is False
        assert card["arvectum_published_android_product_proven"] is False
        assert card["company_authorized_to_submit"] is False
        assert card["human_go"] is False
    assert cases["workspace-19041"]["organizer_type"] == "Юридическое лицо"
    assert cases["workspace-18998"]["organizer_type"] == "Юридическое лицо"
    assert cases["workspace-19007"]["organizer_type"] == "Частное лицо"
    assert cases["workspace-19007"]["is_corporate_candidate"] is False
    assert cases["workspace-19007"]["source_status_gate"] != "PUBLIC_CANDIDATE_ONLY"
    assert cases["workspace-19041"]["original_public_budget_min_rub"] == 250000
    assert cases["workspace-19041"]["original_public_budget_max_rub"] == 1000000
    assert cases["workspace-18998"]["original_public_budget_min_rub"] == 240000
    assert cases["workspace-18998"]["application_deadline_date"] == "2026-10-31"
    assert cases["workspace-19007"]["application_deadline_date"] == "2026-10-20"


def test_mobile_source_requirements_prevent_ios_portfolio_overclaim():
    cases = {x["id"]: x for x in D["current_source_workspace_mobile_cards"]}
    assert "Коммерческий опыт разработки мобильных приложений от 3 лет." in (
        cases["workspace-19041"]["original_literal_requirements"]
    )
    assert "Android 8.1 (API 27), без Google-сервисов" in (
        cases["workspace-18998"]["original_literal_requirements"]
    )
    assert "Файлы для скачивания доступны участникам с PRO-аккаунтом" in (
        cases["workspace-19007"]["original_literal_requirements"]
    )
    assert cases["workspace-19041"]["conservative_mobile_qualification_gate"] == (
        "HARD_MIN_THREE_YEAR_AND_ANDROID_IOS_UNPROVEN"
    )
    assert cases["workspace-19007"]["conservative_mobile_qualification_gate"] == (
        "PERSONAL_ORGANIZER_EXCLUDE_FROM_LLC_B2B"
    )


def test_mobile_source_parser_failclosed_on_personal_to_corporate_mislabelling():
    with pytest.raises(ValueError):
        _card_original_facts(b"not actually an original Workspace card", "19007", datetime.now().astimezone())


def test_pro_cost_premature_purchase_and_illustrative_tax_do_not_claim_profit():
    assert D["cash_lost_if_pro_purchased_and_zero_wins_rub"] == 16900
    assert D["hypothetical_250k_one_contract_remainder_after_pro_and_usn6_before_cost_rub"] == 218100
    assert D["scenario_is_not_profit_and_not_approved_offer"]
    assert not D["owner_pro_purchase_approved"]


def test_owner_report_source_cautions_and_live_portfolio():
    text = (ROOT / "B2B_WORKSPACE_MOBILE_APPSTORE_LLC_REFERENCES_2026-10-17.md").read_text()
    for string in (
        "16 900 ₽", "45 630 ₽", "86 190 ₽", "152 100 ₽",
        "LLC ARVECTUM", "ChickMark", "Фото и PDF под размер",
        "Arvectum Proxy Launcher", "от 3 лет", "без Google-сервисов",
        "Частное лицо", "NO_AUTO_BUY", "218 100 ₽",
    ):
        assert string in text
    assert "не подтверждены" in text or "не подтверждён" in text
