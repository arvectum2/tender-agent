"""Original public Design PRO rate is NOT a quote for the company's cart."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.acceptance.audit_workspace_design_pro_19012_20261018 import (
    ACTIVATION,
    BUDGET,
    DESIGN_URL,
    PIN,
    verify_design_tariffs,
    verify_original_design_card,
)


def _pricing():
    rows = " ".join(" ".join(PIN[k]) for k in ("website", "design", "content"))
    return (
        "<html><body>" + "test " * 260
        + "Заявка на оплату PRO-аккаунта "
        + ACTIVATION + " Опция PRO 1 месяц "
        + rows + " Стоимость: после покупки"
        + "</body></html>"
    ).encode("utf-8")


def _card():
    return (
        "<html><body>" + "test " * 140
        + "<h1>Новый дизайн сайта детских товаров</h1>"
        + '<div class="tendercart-type__status-public">Идет прием заявок</div>'
        + '<span class="reference _public">Публичный</span>'
        + "Дизайн главной страницы сайта детских товаров "
        + "Материалы: ТЗ, прототип, мудборд. "
        + BUDGET
        + " Дизайн сайта "
        + "<p>Крайний срок приема заявок: 19 октября 2026</p>"
        + "<p>Oрганизатор Юридическое лицо</p>"
        + "</body></html>"
    ).encode("utf-8")


def test_first_party_design_branding_tariff_not_website_or_content_rate():
    x = verify_design_tariffs(_pricing())
    assert x["public_design_branding_pro_1mo_rub"] == 6900
    assert x["public_website_development_pro_1mo_rub"] == 25500
    assert x["public_content_pro_1mo_rub"] == 2900
    assert x["design_vs_website_pro_price_difference_rub"] == 18600
    assert "одного рабочего дня" in x["published_activation"]
    assert x["is_design_19012_pro_category_binding_confirmed_in_account"] is False
    assert x["is_user_company_checkout_price_verified"] is False
    assert x["owner_purchased_subscription"] is False


@pytest.mark.parametrize("old,new", [
    ("6 900", "25 500"),
    ("25 500", "2 900"),
    ("2 900", "6 900"),
    ("Опция PRO 1 месяц", "Опция PRO"),
    ("одного рабочего дня", "двух рабочих дней"),
])
def test_first_party_pricing_change_does_not_claim_a_verified_price(old, new):
    with pytest.raises(ValueError):
        verify_design_tariffs(_pricing().replace(old.encode(), new.encode(), 1))


def test_original_design_scope_budget_and_deadline_are_separate_proofs():
    x = verify_original_design_card(_card(), datetime(2026, 10, 18, 6, 0, tzinfo=UTC))
    assert x["original_card_url"] == DESIGN_URL
    assert x["source_budget_floor_rub"] == 100000
    assert x["source_budget_ceiling_rub"] == 400000
    assert x["printed_deadline_day"] == "2026-10-19"
    assert x["deadline_clock_time"] == "UNKNOWN"
    assert x["public_source_state"] == "PUBLIC_CANDIDATE_ONLY"
    assert len(x["original_critical_requirement_excerpts"]) == 3
    assert x["company_portfolio_proven"] is False
    assert x["response_access_from_company_account_proven"] is False


def test_actual_source_budget_drift_fails_closed():
    with pytest.raises(ValueError):
        verify_original_design_card(
            _card().replace(b"100 000 - 400 000", b"800 000 - 900 000"),
            datetime(2026, 10, 18, 6, 0, tzinfo=UTC),
        )


def test_checked_in_source_receipt_never_authorizes_company_payment():
    p = Path(__file__).resolve().parents[1] / "docs/roadmap/b2b_workspace_19012_design_pro_original_2026-10-18.json"
    x = json.loads(p.read_text(encoding="utf-8"))
    assert x["schema_version"] == "ta-b2b-workspace-19012-design-pro-public-price-gate-v1"
    assert len(x["original_card"]["source_html_sha256"]) == 64
    assert len(x["original_official_pro_policy"]["advertising_source_html_sha256"]) == 64
    assert x["design_pro_monthly_fee_to_public_budget_floor_pct_if_applicable"] == "6.9"
    assert x["no_paid_subscription_or_reply_executed"] is True
    assert x["company_owner_go"] is False
    assert x["eligible_tender_bids_confirmed"] == 0
    assert x["activation_before_printed_deadline"] == "NOT_VERIFIED"
    assert x["actual_fee_or_ability_to_reply_from_arvectum_llc_account"] == "NOT_VERIFIED"
