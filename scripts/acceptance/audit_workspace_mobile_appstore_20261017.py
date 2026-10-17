"""Official Workspace mobile PRO, original cards, and Apple LLC portfolio.

Read only public first-party pages and Apple catalog. App Store publications
show shipped iOS products, NOT 3y client-contract history or Android delivery.
No account access, paid PRO, bids or external messages.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

if __package__ in (None, "") and __file__ != "<stdin>":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.acceptance.audit_workspace_oct17_cards import extract_public_card
from scripts.acceptance.audit_workspace_official_pro_tariff_oct17 import (
    extract_official_prices,
)

_PRICES_URL = "https://workspace.ru/advertising/"
_TENDER_CARDS = {
    "19041": (
        "sozdanie-mobilnogo-prilozheniya-dlya-myasokombinata",
        "2026-10-31", "FIT_HIGH",
        (
            "Разработка мобильного приложения для Android и iOS.",
            "Коммерческий опыт разработки мобильных приложений от 3 лет.",
            "Наличие портфолио с завершёнными и действующими проектами.",
            "Передача исходного кода, документации и необходимых доступов заказчику",
        ),
        "HARD_MIN_THREE_YEAR_AND_ANDROID_IOS_UNPROVEN",
        (250_000, 1_000_000),
    ),
    "18998": (
        "prilozhenie-s-golosovym-ii-pitomcem-dlya-detskih-4g-smart-chasov-android-8-1-bez-google-servisov-server",
        "2026-10-31", "FIT_REVIEW",
        (
            "Android 8.1 (API 27), без Google-сервисов",
            "Приёмка — только на реальных часах с SIM-картой",
            "GigaChat",
            "152-ФЗ",
        ),
        "ANDROID_NO_GMS_HARDWARE_AND_CHILDREN_SAFETY_UNVERIFIED",
        (240_000, 1_000_000),
    ),
    "19007": (
        "platforma-yuridicheskoy-pomoschi",
        "2026-10-20", "EXCLUDE_PERSONAL_ORGANIZER",
        (
            "приложения iOS и Android, веб-версию и административную панель",
            "рынка Казахстана",
            "Файлы для скачивания доступны участникам с PRO-аккаунтом",
        ),
        "PERSONAL_ORGANIZER_EXCLUDE_FROM_LLC_B2B",
        (1_500_000, None),
    ),
}
_APP_IDS = {
    "6818711298": "ChickMark: трекер привычек",
    "6816346084": "Фото и PDF под размер",
    "6816013574": "Arvectum Proxy Launcher",
}
_MAX_SOURCE = 410_000
_USN_ILLUSTRATIVE_GROSS = Decimal("0.06")


def _raw_read(opener: object, url: str, *, cap: int = _MAX_SOURCE) -> bytes:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in (
        "workspace.ru", "itunes.apple.com"
    ):
        raise ValueError("not an approved public first-party source")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("unexpected source credentials")
    req = Request(url, headers={"User-Agent": "ArvectumTenderAgent-SourceResearch/1.0"})
    with opener.open(req, timeout=13) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("source unavailable or redirected")
        raw = response.read(cap + 1)
    if not 500 < len(raw) <= cap:
        raise ValueError("source size rejected")
    return raw


def _card_original_facts(raw: bytes, number: str, observed: datetime) -> dict:
    slug, deadline, decision, quotations, fit, budget = _TENDER_CARDS[number]
    card = extract_public_card(
        raw, key=number, observed=observed,
        allowed_cards={number: (slug, deadline, decision)},
    )
    plain = " ".join(html.unescape(re.sub(
        r"<[^>]+>", " ", raw.decode("utf8", "strict")
    )).split())
    for quotation in quotations:
        if quotation.casefold() not in plain.casefold():
            raise ValueError("original card no longer substantiates qualification fact")
    if card["visibility"] != "public" or card["platform_status"] != "Идет прием заявок":
        raise ValueError("current original public acceptance gate changed")
    if number == "19007":
        if card["organizer_type"] != "Частное лицо" or card["source_status_gate"] == "PUBLIC_CANDIDATE_ONLY":
            raise ValueError("misclassified personal organizer as corporate")
    elif card["organizer_type"] != "Юридическое лицо" or card["source_status_gate"] != "PUBLIC_CANDIDATE_ONLY":
        raise ValueError("original corporate applicant source not accepting")
    return {
        **card,
        "original_literal_requirements": list(quotations),
        "original_public_budget_min_rub": budget[0],
        "original_public_budget_max_rub": budget[1],
        "conservative_mobile_qualification_gate": fit,
        "is_corporate_candidate": number != "19007",
        "full_locked_tender_spec_inspected": False,
        "our_own_three_year_commercial_mobile_contract_history_proven": False,
        "arvectum_published_android_product_proven": False,
        "company_authorized_to_submit": False,
    }


def _apple_original_facts(raw: bytes, app_id: str) -> dict:
    original = json.loads(raw)
    if original.get("resultCount") != 1 or len(original.get("results", [])) != 1:
        raise ValueError("original Apple record ambiguous")
    app = original["results"][0]
    if (str(app.get("trackId")) != app_id or app.get("kind") != "software"
        or app.get("sellerName") != "LLC ARVECTUM"
        or app.get("trackName") != _APP_IDS[app_id]):
        raise ValueError("not proved seller-owned shipped Apple app")
    link = app.get("trackViewUrl")
    parsed = urlsplit(link)
    if parsed.scheme != "https" or parsed.hostname != "apps.apple.com" or f"id{app_id}" not in parsed.path:
        raise ValueError("untrusted Apple storefront link")
    return {
        "app_store_numeric_id": int(app_id),
        "track_name": app["trackName"],
        "app_store_link": f"https://apps.apple.com/ru/app/id{app_id}",
        "first_party_recorded_seller": "LLC ARVECTUM",
        "first_party_artist": app.get("artistName"),
        "published_version_at_observation": app.get("version"),
        "country_lookup": "ru",
        "verified_official_apple_lookup_http200": True,
        "official_apple_lookup_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "published_client_commissioning_proven": False,
        "three_year_commercial_development_duration_proven": False,
        "android_delivery_proven": False,
    }


def collect() -> dict:
    opener = build_opener(ProxyHandler({}))
    source_pricing = _raw_read(opener, _PRICES_URL)
    table = extract_official_prices(source_pricing)["original_public_prices_rub_total"]
    mobile = table["app_development"]
    if mobile != {
        "1_month": 16900, "3_months": 45630,
        "6_months": 86190, "12_months": 152100,
    }:
        raise ValueError("Workspace official mobile advertised category prices changed")
    apps = []
    for app_id in _APP_IDS:
        source = f"https://itunes.apple.com/lookup?id={app_id}&country=ru&entity=software"
        raw = _raw_read(opener, source)
        apps.append(_apple_original_facts(raw, app_id))
    cards = []
    for number, (slug, _, _, _, _, _) in _TENDER_CARDS.items():
        url = f"https://workspace.ru/tenders/{slug}-{number}/"
        raw = _raw_read(opener, url)
        cards.append(_card_original_facts(raw, number, datetime.now(UTC)))
    return {
        "schema_version": "arvectum-firstparty-apple-workspace-mobile-b2b-20261017-v1",
        "as_of_date": "2026-10-17",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "workspace_official_pro_category_source": _PRICES_URL,
        "workspace_official_pro_html_sha256": hashlib.sha256(source_pricing).hexdigest(),
        "workspace_app_development_product_code": "MOB",
        "original_advertised_app_category_PRO_rub": mobile,
        "original_advertised_app_PRO_1_month_rub": 16900,
        "generic_cheapest_content_category_not_app_price_rub": 2900,
        "verified_official_apple_company_portfolio": apps,
        "verified_llc_apple_published_product_count": len(apps),
        "verified_android_client_delivery_count": 0,
        "current_source_workspace_mobile_cards": cards,
        "current_public_corporate_mobile_candidates": 2,
        "excluded_personal_organizers": 1,
        "arvectum_mobile_bid_ready_count": 0,
        "owner_pro_purchase_approved": False,
        "platform_authenticated_account_mobile_category_verified": False,
        "owner_company_eligibility_verified": False,
        "cash_lost_if_pro_purchased_and_zero_wins_rub": 16900,
        "hypothetical_250k_one_contract_remainder_after_pro_and_usn6_before_cost_rub": int(
            Decimal(250000) * (1 - _USN_ILLUSTRATIVE_GROSS) - Decimal(16900)
        ),
        "scenario_is_not_profit_and_not_approved_offer": True,
        "no_external_bids_registration_payment_or_new_ui": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.name != "b2b_workspace_mobile_appstore_original_2026-10-17.json":
        parser.error("write only dated first-party source receipt")
    output = collect()
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print("LLC_APPSTORE_REAL_PUBLIC_REFERENCES", output["verified_llc_apple_published_product_count"],
          "MOBILE_PRO_1_MONTH", output["original_advertised_app_PRO_1_month_rub"],
          "LIVE_SOURCE_CORPORATE", output["current_public_corporate_mobile_candidates"],
          "BID_GO", output["arvectum_mobile_bid_ready_count"])


if __name__ == "__main__":
    main()
