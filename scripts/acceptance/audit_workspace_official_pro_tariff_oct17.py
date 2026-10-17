"""Source-only Workspace PRO category prices; NEVER run checkout or login.

Official advertising page is a public preview of 1/3/6/12mo selected products,
not proof of account-specific cart price, eligibility, or guaranteed tender win.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

_URL = "https://workspace.ru/advertising/"
_CODES = {
    "site_development": "WEB_DEV",
    "app_development": "MOB",
    "crm_software_1c_ai": "CRM",
    "content_teaser_cheapest_category": "CNTNT",
}
_DURATION = (("1_month", "1_MON"), ("3_months", "3_MON"),
             ("6_months", "6_MON"), ("12_months", "1_Y"))
_MAX_SIZE = 350_000
_OFFER = Decimal(89000)
_BUYER_PUBLIC_MIN = Decimal(130000)
_USN_PLANNING_GROSS_RATE = Decimal("0.06")


def _price_for_code(source: str, code: str) -> int:
    # The original page anchors each price to an input value and the next
    # official calculator span. Reject missing, duplicated or malformed prices.
    pattern = (
        r'<input\b[^>]*\bvalue="' + re.escape(code) +
        r'"[^>]*>\s*<span\s+data-calc-price-val="([^"]+)">([0-9\s]+)</span>'
    )
    matches = re.findall(pattern, source)
    if len(matches) != 1:
        raise ValueError("exact original PRO tariff code missing/ambiguous")
    title, value = matches[0]
    if "PRO-аккаунт" not in title:
        raise ValueError("original product is not PRO")
    price = int(re.sub(r"\s", "", value))
    if price < 1000 or price > 500_000:
        raise ValueError("unexpected first-party public price")
    return price


def extract_official_prices(raw: bytes) -> dict:
    if not 40_000 < len(raw) <= _MAX_SIZE:
        raise ValueError("unrecognized original advertising HTML size")
    source = raw.decode("utf8", "strict")
    if "PRO-аккаунты — это платная опция" not in html.unescape(source):
        raise ValueError("original advertised product not proven")
    if "от <b>2 900 ₽</b> / месяц" not in source:
        raise ValueError("unrecognized generic teaser")
    table = {}
    for name, prefix in _CODES.items():
        table[name] = {
            span: _price_for_code(source, f"{prefix}_{code}")
            for span, code in _DURATION
        }
    assert table["content_teaser_cheapest_category"]["1_month"] == 2900
    site = table["site_development"]["1_month"]
    crm = table["crm_software_1c_ai"]["1_month"]
    return {
        "original_public_prices_rub_total": table,
        "generic_advertised_from_rub_per_month": 2900,
        "site_one_month_price_rub": site,
        "crm_ai_one_month_price_rub": crm,
        "offer_published_rub": int(_OFFER),
        "owner_schlam_entrance_offer_less_site_one_month_PRO_rub": int(_OFFER-site),
        "site_one_month_pro_share_of_offer_percent": str(
            ((Decimal(site)/_OFFER)*100).quantize(Decimal("0.01"))
        ),
        "site_one_month_plus_illustrative_usn6pct_gross_on_offer_rub": int(
            Decimal(site)+_OFFER*_USN_PLANNING_GROSS_RATE
        ),
        "offer_after_site_pro_and_illustrative_usn_before_any_other_cost_rub": int(
            _OFFER - Decimal(site) - _OFFER*_USN_PLANNING_GROSS_RATE
        ),
        "buyer_public_budget_min_rub": int(_BUYER_PUBLIC_MIN),
        "buyer_budget_min_after_site_pro_and_illustrative_usn_before_cost_rub": int(
            _BUYER_PUBLIC_MIN - Decimal(site) - _BUYER_PUBLIC_MIN*_USN_PLANNING_GROSS_RATE
        ),
    }


def collect() -> dict:
    opener = build_opener(ProxyHandler({}))
    with opener.open(
        Request(_URL, headers={"User-Agent": "ArvectumTenderAgent-ReadOnlyPrice/1.0"}),
        timeout=12,
    ) as response:
        if response.status != 200 or response.geturl() != _URL:
            raise ValueError("original public price page not available")
        original = response.read(_MAX_SIZE + 1)
    if urlsplit(_URL).hostname != "workspace.ru":
        raise ValueError("only authentic original source supported")
    data = extract_official_prices(original)
    return {
        "schema_version": "workspace-firstparty-pro-advertising-category-price-v1",
        "source_url": _URL,
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "original_html_sha256": hashlib.sha256(original).hexdigest(),
        "original_html_length_bytes": len(original),
        "original_http": 200,
        **data,
        "source_prices_are_public_advertising_not_authenticated_cart": True,
        "actual_company_plan_and_category_entitlement_unknown": True,
        "pro_purchase_authorized": False,
        "paid_no_win_cash_risk_site_month_rub": data["site_one_month_price_rub"],
        "actual_invoice_or_vat_treatment_proven": False,
        "usn6pct_illustration_not_verified_company_tax_or_vat_advice": True,
        "gross_left_before_labor_hosting_ip_legal_support_and_all_other_expenses": True,
        "owner_go": False,
        "external_action_executed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.name != "b2b_workspace_original_pro_prices_2026-10-17.json":
        parser.error("only date-pinned research source receipt permitted")
    data = collect()
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print("OFFICIAL_PRO_SITE_MONTH",data["site_one_month_price_rub"],
          "CRM_AI_MONTH",data["crm_ai_one_month_price_rub"],
          "GENERIC_TEASER",data["generic_advertised_from_rub_per_month"],
          "OWNER_GO",data["owner_go"])


if __name__ == "__main__":
    main()
