"""First-party demand vs self-advertisement, with no false LLC readiness."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.acceptance.audit_free_first_real_customer_20261018 import (
    _CODELANCE,
    _CONTRACTIS,
    _exact_original,
    discover_exact_listed,
    evaluate_original,
)

SNAPSHOT = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "docs/roadmap/b2b_free_first_real_customer_originals_2026-10-18.json"
    ).read_text(encoding="utf-8")
)
NOW = datetime(2026, 10, 18, tzinfo=UTC)


def _code_html(anchor: str, status: str = "Открыт", *, put_in_brief: bool = True) -> bytes:
    content = anchor if put_in_brief else "Описания заказа не представлено"
    rest = anchor if not put_in_brief else ""
    return (
        "<html><body>Оригинальная карточка " + status
        + " Заказ Веб-разработка Раздел Что нужно "
        + content + " Ваш отклик "
        + rest + " заказ рекламных блоков"
        + ("тест " * 300) + "</body></html>"
    ).encode("utf-8")


def _contractis_html(number: int, anchor: str) -> bytes:
    return (
        f"<html><body>Заказ № {number} Заказчик ООО? НЕИЗВЕСТНО "
        + "Программирование и IT Дата публикации: неизвестно Описание "
        + anchor + " Общее О бирже"
        + ("тест " * 300) + "</body></html>"
    ).encode("utf-8")


def test_exact_source_identity_forbids_account_urls_tracking_and_other_hosts():
    accepted = "https://www.codelance.ru/orders/view?id=147"
    assert _exact_original(accepted, "codelance") == "147"
    assert _exact_original(
        "https://contractis.ru/order/sait-dlya-padl-kluba-lending-s-bronirovaniem", "contractis",
    ) == "sait-dlya-padl-kluba-lending-s-bronirovaniem"
    for url in (
        "https://www.codelance.ru/orders/view?id=147&return=account",
        "https://www.codelance.ru/orders/view?id=147&foo=",
        "https://www.codelance.ru/orders/view?id=147#reply",
        "https://www.codelance.ru/orders/view?id=147&id=150",
        "http://www.codelance.ru/orders/view?id=147",
        "https://contractis.ru/order/create",
        "https://contractis.ru/order/your",
        "https://contractis.ru/order/foo/?q=1",
        "https://contractis.ru@evil.example/order/foo",
    ):
        assert _exact_original(url, "codelance") is None
        assert _exact_original(url, "contractis") is None


def test_code_lance_open_self_ad_is_never_a_real_customer_request():
    identity = 154
    cls, anchor = _CODELANCE[identity]
    assert cls == "SELF_ADVERTISEMENT"
    result = evaluate_original(
        _code_html(anchor), "codelance",
        "https://www.codelance.ru/orders/view?id=154", NOW,
    )
    assert result["original_status_literal_or_gap"] == "Открыт"
    assert result["source_role"] == "SELF_ADVERTISEMENT"
    assert result["customer_gate"] == "EXCLUDED_FROM_CUSTOMER_LEADS"
    assert result["free_llc_reply_entitlement_verified"] is False
    assert result["legal_company_contract_permission_verified"] is False


def test_code_lance_actual_feed_import_scope_is_only_unverified_customer():
    _, anchor = _CODELANCE[147]
    r = evaluate_original(
        _code_html(anchor), "codelance",
        "https://www.codelance.ru/orders/view?id=147", NOW,
    )
    assert r["source_role"] == "CUSTOMER_IT_REQUEST_STATUS_UNVERIFIED"
    assert r["customer_gate"] == "CLIENT_REQUEST_CONTENT_ATTESTED_CURRENT_REPLY_UNVERIFIED"
    assert r["legal_company_buyer_inn_verified"] is False
    assert r["free_llc_reply_entitlement_verified"] is False
    assert r["company_offer_sent"] is False


def test_self_promo_anchor_only_in_similar_card_is_rejected():
    _, anchor = _CODELANCE[154]
    with pytest.raises(ValueError, match="evidence changed"):
        evaluate_original(
            _code_html(anchor, put_in_brief=False), "codelance",
            "https://www.codelance.ru/orders/view?id=154", NOW,
        )


def test_contractis_original_customer_needs_order_identity_not_owner_entity_guess():
    slug = "sait-dlya-padl-kluba-lending-s-bronirovaniem"
    number, _, anchor = _CONTRACTIS[slug]
    r = evaluate_original(
        _contractis_html(number, anchor),
        "contractis", "https://contractis.ru/order/" + slug, NOW,
    )
    assert r["source_role"] == "CUSTOMER_IT_REQUEST_STATUS_UNVERIFIED"
    assert r["original_status_literal_or_gap"] == "CURRENT_APPLICATION_STATUS_NOT_EXPLICITLY_VERIFIED"
    assert r["legal_company_contract_permission_verified"] is False
    assert r["free_llc_reply_entitlement_verified"] is False
    with pytest.raises(ValueError, match="identity"):
        evaluate_original(
            _contractis_html(13, anchor),
            "contractis", "https://contractis.ru/order/" + slug, NOW,
        )


def test_original_contractis_catalog_cards_category_not_proof_of_it_delivery():
    slug = "trebuetsya-specialist-po-sozdaniyu-kartochek-tovarov-dlya-wi"
    number, category, anchor = _CONTRACTIS[slug]
    assert category == "NOT_IT_CONTRACT_WORK"
    r = evaluate_original(
        _contractis_html(number, anchor),
        "contractis", "https://contractis.ru/order/" + slug, NOW,
    )
    assert r["customer_gate"] == "EXCLUDED_FROM_CUSTOMER_LEADS"


def test_changed_original_listing_never_promoted():
    html = (
        "<html>" + "a" * 1500
        + '<a href="/orders/view?id=147">Source</a>'
        + '<a href="/orders/view?id=147">Duplicate</a>'
        + '<a href="/orders/view?id=999">Unreviewed</a>'
        + "</html>"
    ).encode("utf8")
    with pytest.raises(ValueError, match="index list materially changed"):
        discover_exact_listed(html, "codelance")


def test_snapshot_counts_are_not_bogus_ten_new_company_clients():
    r = SNAPSHOT
    assert r["schema_version"] == "ta-b2b-free-first-source-role-originals-2026-10-18-v1"
    assert r["original_listed_unique_cards"] == 19
    assert len({item["original_id"] for item in r["rows"]}) == 19
    assert r["original_customer_it_scope_descriptions"] == 7
    assert r["verified_company_bidding_ready_count"] == 0
    assert r["original_status_and_llc_reply_both_verified_count"] == 0
    assert r["actual_free_llc_first_reply_count"] == 0
    assert r["outgoing_communications_or_paid_actions"] == 0
    roles = [row["source_role"] for row in r["rows"]]
    assert roles.count("SELF_ADVERTISEMENT") == 9
    assert roles.count("NOT_IT_CONTRACT_WORK") == 2
    assert roles.count("REJECT_RISK_OR_OUT_OF_SCOPE") == 1
    assert roles.count("CUSTOMER_IT_REQUEST_STATUS_UNVERIFIED") == 7
    assert len(r["first_party_indices"]) == 2
    assert all(not x["company_offer_sent"] for x in r["rows"])
    assert all(not x["paid_subscription_or_registration"] for x in r["rows"])
    for item in r["rows"]:
        assert len(item["original_html_sha256"]) == 64
        assert item["legal_company_contract_permission_verified"] is False
        assert item["free_llc_reply_entitlement_verified"] is False
    # Three previously inspected originals must not inflate net new leads.
    prior = {"contractis:6", "contractis:8", "codelance:147"}
    assert prior.issubset({x["original_id"] for x in r["rows"]})
    new = {
        x["original_id"] for x in r["rows"]
        if x["source_role"] == "CUSTOMER_IT_REQUEST_STATUS_UNVERIFIED"
    } - prior
    assert new == {"contractis:12", "contractis:5", "contractis:4", "contractis:2"}
