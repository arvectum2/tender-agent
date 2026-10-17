"""Fail-closed, first-party Workspace PRO prices and no-bid cash gates."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from scripts.acceptance.audit_workspace_official_pro_tariff_oct17 import (
    _price_for_code,
    extract_official_prices,
)

ROOT = Path(__file__).resolve().parents[1] / "docs/roadmap"
DATA = json.loads((ROOT / "b2b_workspace_original_pro_prices_2026-10-17.json").read_text())


def test_actual_original_advertising_page_category_prices_not_generic_teaser():
    assert DATA["schema_version"] == "workspace-firstparty-pro-advertising-category-price-v1"
    assert DATA["source_url"] == "https://workspace.ru/advertising/"
    assert DATA["original_http"] == 200
    assert re.fullmatch("[0-9a-f]{64}", DATA["original_html_sha256"])
    assert 40000 < DATA["original_html_length_bytes"] <= 350000
    assert datetime.fromisoformat(DATA["checked_at_utc"]).tzinfo is not None
    assert DATA["generic_advertised_from_rub_per_month"] == 2900
    assert DATA["site_one_month_price_rub"] == 25500
    assert DATA["crm_ai_one_month_price_rub"] == 6900
    assert DATA["site_one_month_price_rub"] > DATA["generic_advertised_from_rub_per_month"]


@pytest.mark.parametrize(("name", "months"), [
    ("site_development", [25500, 68850, 130050, 229500]),
    ("app_development", [16900, 45630, 86190, 152100]),
    ("crm_software_1c_ai", [6900, 18630, 35190, 62100]),
    ("content_teaser_cheapest_category", [2900, 7830, 14790, 26100]),
])
def test_original_first_party_four_duration_prices(name, months):
    row = DATA["original_public_prices_rub_total"][name]
    assert [row[k] for k in ("1_month", "3_months", "6_months", "12_months")] == months


def test_schlam_offer_expense_upper_limits_not_false_net_profit():
    assert DATA["offer_published_rub"] == 89000
    assert DATA["buyer_public_budget_min_rub"] == 130000
    assert DATA["paid_no_win_cash_risk_site_month_rub"] == 25500
    assert DATA["owner_schlam_entrance_offer_less_site_one_month_PRO_rub"] == 63500
    assert DATA["site_one_month_pro_share_of_offer_percent"] == "28.65"
    assert DATA["site_one_month_plus_illustrative_usn6pct_gross_on_offer_rub"] == 30840
    assert DATA["offer_after_site_pro_and_illustrative_usn_before_any_other_cost_rub"] == 58160
    assert DATA["buyer_budget_min_after_site_pro_and_illustrative_usn_before_cost_rub"] == 96700
    assert DATA["gross_left_before_labor_hosting_ip_legal_support_and_all_other_expenses"] is True
    assert DATA["source_prices_are_public_advertising_not_authenticated_cart"] is True
    assert DATA["actual_company_plan_and_category_entitlement_unknown"] is True
    assert DATA["pro_purchase_authorized"] is False
    assert DATA["actual_invoice_or_vat_treatment_proven"] is False
    assert DATA["usn6pct_illustration_not_verified_company_tax_or_vat_advice"] is True
    assert DATA["owner_go"] is False and DATA["external_action_executed"] is False


def test_source_code_price_parser_rejects_ambiguous_or_malformed_products():
    html = (
        '<input value="WEB_DEV_1_MON" type="checkbox">'
        '<span data-calc-price-val="PRO-аккаунт на разработку сайтов (1 мес.)">'
        "25 500</span>"
    )
    assert _price_for_code(html, "WEB_DEV_1_MON") == 25500
    with pytest.raises(ValueError):
        _price_for_code(html + html, "WEB_DEV_1_MON")
    with pytest.raises(ValueError):
        _price_for_code(html.replace("25 500", "2 900"), "WEB_DEV_2_MON")
    with pytest.raises(ValueError):
        _price_for_code(html.replace("PRO-аккаунт", "free demo"), "WEB_DEV_1_MON")


def test_complete_source_parser_does_not_accept_fake_small_source():
    with pytest.raises(ValueError):
        extract_official_prices(b"<html>PRO 2900 sites 25500</html>")


def test_human_report_is_source_grounded_and_cost_is_not_profit():
    text = (ROOT / "B2B_WORKSPACE_PRO_REAL_SOURCE_COST_GATE_2026-10-17.md").read_text()
    for phrase in ("25 500 ₽", "6 900 ₽", "от 2 900 ₽", "89 000 ₽",
                   "58 160 ₽", "не прибыль", "NO_AUTO_BUY", "не подтверждены"):
        # Profit is stated as a pre-cost residual, not literal word "profit".
        if phrase == "не прибыль":
            assert "до всех остальных затрат" in text
        else:
            assert phrase in text
    assert "без подтверждённых сделок" in text
