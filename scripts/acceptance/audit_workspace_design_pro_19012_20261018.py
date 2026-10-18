"""First-party PRO cost/activation gate for design-only 19012; never purchase."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from scripts.acceptance.audit_schlam_offer_original_oct17 import _Markup
from scripts.acceptance.discover_workspace_original_it_20261018 import (
    _get,
    evaluate_original_card,
)

DESIGN_URL = "https://workspace.ru/tenders/novyy-dizayn-sayta-detskih-tovarov-19012/"
PRO_PRICING_URL = "https://workspace.ru/advertising/"
PIN = {
    "design": ("Дизайн и брендинг", "6 900 18 630 35 190 62 100"),
    "website": ("Разработка сайтов", "25 500 68 850 130 050 229 500"),
    "content": ("Контент", "2 900 7 830 14 790 26 100"),
}
ACTIVATION = "Опция будет подключена в течение одного рабочего дня после оплаты."
BUDGET = "Бюджет: 100 000 - 400 000 рублей"


def _plain(body: bytes) -> str:
    markup = _Markup()
    markup.feed(body.decode("utf-8", "strict"))
    return markup.text


def verify_design_tariffs(body: bytes) -> dict:
    if not 1000 <= len(body) <= 250_000:
        raise ValueError("official PRO policy size invalid")
    text = _plain(body)
    marker = "Заявка на оплату PRO-аккаунта"
    if text.count(marker) != 1:
        raise ValueError("PRO pricing table ambiguous")
    section = text.split(marker, 1)[1].split("Стоимость:", 1)[0]
    if section.count(ACTIVATION) != 1:
        raise ValueError("PRO activation notice unavailable")
    for name, (label, fees) in PIN.items():
        if section.count(label + " " + fees) != 1:
            raise ValueError(f"first-party price row {name} absent or changed")
    if "Опция PRO 1 месяц" not in section:
        raise ValueError("unidentified monthly PRO price column")
    return {
        "advertising_source_html_sha256": hashlib.sha256(body).hexdigest(),
        "public_design_branding_pro_1mo_rub": 6900,
        "public_website_development_pro_1mo_rub": 25500,
        "public_content_pro_1mo_rub": 2900,
        "design_vs_website_pro_price_difference_rub": 18600,
        "published_activation": ACTIVATION,
        "is_user_company_checkout_price_verified": False,
        "is_design_19012_pro_category_binding_confirmed_in_account": False,
        "owner_purchased_subscription": False,
    }


def verify_original_design_card(body: bytes, observed: datetime) -> dict:
    row = evaluate_original_card(
        number="19012", slug="novyy-dizayn-sayta-detskih-tovarov",
        original_url=DESIGN_URL, body=body, observed=observed,
        categories=("WEB",),
    )
    if (
        row["public_source_state"] != "PUBLIC_CANDIDATE_ONLY"
        or row["scope_attestation_state"] != "PRIORITY_ORIGINAL_REQUIREMENTS_ATTESTED"
        or row["printed_deadline_day"] != "2026-10-19"
        or row["organizer_type"] != "Юридическое лицо"
    ):
        raise ValueError("urgent design original not currently attested")
    text = _plain(body)
    if text.count(BUDGET) != 1 or "Дизайн сайта" not in text:
        raise ValueError("original design budget/category not attested")
    return {
        "original_card_url": DESIGN_URL,
        "source_html_sha256": row["source_sha256"],
        "checked_at_utc": observed.isoformat(),
        "public_source_state": row["public_source_state"],
        "printed_deadline_day": row["printed_deadline_day"],
        "deadline_clock_time": "UNKNOWN",
        "source_budget_floor_rub": 100000,
        "source_budget_ceiling_rub": 400000,
        "advertised_service": "Дизайн сайта",
        "original_critical_requirement_excerpts": list(row["original_required_scope_fragments"]),
        "company_portfolio_proven": False,
        "response_access_from_company_account_proven": False,
    }


def collect() -> dict:
    card = verify_original_design_card(_get(DESIGN_URL, max_bytes=400_000), datetime.now(UTC))
    pro = verify_design_tariffs(_get(PRO_PRICING_URL, max_bytes=250_000))
    price = Decimal(pro["public_design_branding_pro_1mo_rub"])
    budget = Decimal(card["source_budget_floor_rub"])
    return {
        "schema_version": "ta-b2b-workspace-19012-design-pro-public-price-gate-v1",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "original_card": card,
        "original_official_pro_policy_url": PRO_PRICING_URL,
        "original_official_pro_policy": pro,
        "design_pro_monthly_fee_to_public_budget_floor_pct_if_applicable": str(price * 100 / budget),
        "actual_fee_or_ability_to_reply_from_arvectum_llc_account": "NOT_VERIFIED",
        "activation_before_printed_deadline": "NOT_VERIFIED",
        "cash_cost_if_no_wins": "UNKNOWN_UNTIL_OWNER_DECIDES_TO_BUY",
        "no_paid_subscription_or_reply_executed": True,
        "company_owner_go": False,
        "eligible_tender_bids_confirmed": 0,
    }


def main() -> None:
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--out", required=True, type=Path)
    a = arg.parse_args()
    x = collect()
    a.out.write_text(json.dumps(x, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ORIGINAL_DESIGN_DUE", x["original_card"]["printed_deadline_day"],
          "OFFICIAL_DESIGN_PRO_MONTH", x["original_official_pro_policy"]["public_design_branding_pro_1mo_rub"],
          "LLC_GO", x["company_owner_go"])


if __name__ == "__main__":
    main()
