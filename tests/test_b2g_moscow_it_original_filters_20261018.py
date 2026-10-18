"""No custom-development or company eligibility from title-wide IT-goods search."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.acceptance.audit_moscow_it_original_details_20261018 import (
    SOURCE_CASES,
    audit_public_search_observation,
    verify_original,
)

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = json.loads(
    (
        ROOT / "docs/roadmap/b2g_moscow_6_queries_and_3_original_goods_2026-10-18.json"
    ).read_text("utf-8")
)

TERMS = (
    "программного обеспечения", "создание сайта", "информационной системы",
    "сопровождение", "разработка сайта", "программирование",
)
NOW = datetime(2026, 10, 18, 8, 10, tzinfo=UTC)


def _synthetic_search():
    items = []
    for term in TERMS:
        items.append({
            "term": term,
            "exact_applied_query": True,
            "public_status_gate": [19000002],
            "first_page_only": True,
            "html_public_visible_text": "Ничего не нашлось",
            "original_detail_links": [],
        })
    return {"state": "PUBLIC_FIRST_PARTY_IT_SEARCH_COMPLETED", "searches": items}


def _synthetic_original(number):
    case = SOURCE_CASES[number]
    return (
        "<html><head><title>Котировочная сессия " + number
        + " «Товары ИТ» на Портале поставщиков</title></head><body>"
        + "<div>Котировочная сессия " + number + " Активная</div>"
        + " <div>Заказчик " + case["buyer"] + "</div>"
        + " <div>Даты проведения по 19.10.2026 13:42:20</div>"
        + " <div>Для участия в котировочной сессии необходимо авторизоваться</div>"
        + " ".join(case["exact_products"])
        + '<a href="https://zakupki.mos.ru/newapi/api/FileStorage/Download?id=12345">'
        + "Техническое задание.docx</a>" + ("index " * 5000) + "</body></html>"
    )


def test_original_goods_classify_only_specific_known_three_ids():
    assert len(SOURCE_CASES) == 3
    assert set(SOURCE_CASES) == {"10321203", "10321182", "10321235"}
    for number in SOURCE_CASES:
        row = verify_original(number, _synthetic_original(number), NOW)
        assert row["exact_original_url"] == "https://zakupki.mos.ru/auction/" + number
        assert row["is_custom_software_development_contract"] is False
        assert row["verified_company_can_respond"] is False
        assert row["original_attached_files_downloaded"] is False
        assert row["company_bidding_requires_authorization_in_source"] is True
        assert len(row["original_rendered_html_sha256"]) == 64
        assert row["original_visible_document_labels"][0]["display_label"] == (
            "Техническое задание.docx"
        )


@pytest.mark.parametrize("change", [
    lambda s: s.replace("Активная", "Завершена"),
    lambda s: s.replace("необходимо авторизоваться", "авторизация не нужна"),
    lambda s: s.replace("19.10.2026", "19.10.2025"),
    lambda s: s.replace("Системный блок BigTech PC S5006", "Поставка несвязанного товара"),
])
def test_changed_actual_original_is_not_verified(change):
    html = change(_synthetic_original("10321203"))
    with pytest.raises(ValueError):
        verify_original("10321203", html, NOW)


def test_unseen_original_cannot_be_read_or_approved():
    with pytest.raises(ValueError):
        verify_original("99999999", _synthetic_original("10321203"), NOW)


def test_six_approved_public_ui_filters_are_strictly_checked():
    sample = _synthetic_search()
    result = audit_public_search_observation(sample)
    assert result["number_of_queries"] == 6
    assert all(row["state_gate_active_public"] for row in result["queries"])
    assert all(row["explicit_no_results_page"] for row in result["queries"])
    assert all(row["source_first_page_only"] for row in result["queries"])


@pytest.mark.parametrize("edit", [
    lambda s: s["searches"][0].update(exact_applied_query=False),
    lambda s: s["searches"][1].update(public_status_gate=[]),
    lambda s: s["searches"][2].update(first_page_only=False),
    lambda s: s["searches"][3].update(term="совсем другой запрос"),
    lambda s: s["searches"][4].update(original_detail_links=[
        {"url": "https://evil.example/auction/10321203", "label": "fake"}
    ]),
    lambda s: s["searches"][5].update(
        html_public_visible_text="Нет исходного подтверждения отказа"
    ),
])
def test_false_filter_params_or_unverified_results_rejected(edit):
    data = _synthetic_search()
    edit(data)
    with pytest.raises(ValueError):
        audit_public_search_observation(data)


def test_real_six_query_receipt_has_no_false_custom_dev_or_b2b():
    r = RECEIPT
    assert r["schema_version"] == (
        "ta-b2g-moscow-public-original-it-keyword-filter-2026-10-18-v1"
    )
    assert r["query_count"] == 6
    assert r["public_registry_real_ui_filters_applied"] is True
    assert r["public_auction_active_state_code_from_visible_page"] == 19000002
    assert [s["exact_public_term"] for s in r["search_result_filters"]] == list(TERMS)
    assert all(s["state_gate_active_public"] for s in r["search_result_filters"])
    assert all(s["source_first_page_only"] for s in r["search_result_filters"])
    assert r["search_result_filters"][1]["explicit_no_results_page"] is True
    assert r["search_result_filters"][5]["explicit_no_results_page"] is True
    assert r["original_detail_pages_verified"] == 3
    assert len({row["id"] for row in r["original_details"]}) == 3
    assert r["current_it_custom_development_scope_originals_verified"] == 0
    assert r["claim_that_no_more_it_auctions_exist"] is False
    assert r["company_full_registration_or_ukep_tested"] is False
    assert r["company_able_to_bid_verified"] is False
    assert r["current_eligible_b2b_increment"] == 0
    assert r["outgoing_actions_or_payments"] == 0
    assert r["disposable_browser_profile_saved"] is False
    for item in r["original_details"]:
        assert len(item["original_rendered_html_sha256"]) == 64
        assert item["is_custom_software_development_contract"] is False
        assert item["verified_company_can_respond"] is False
        assert item["original_visible_document_labels"]


def test_ui_script_cannot_submit_bids_or_guess_api():
    script = (
        ROOT / "scripts/acceptance/audit_moscow_public_it_filter_20261018.mjs"
    ).read_text()
    assert "Показать фильтры" in script
    assert "filterNameLike" in script
    assert "Применить" in script
    assert "Input.insertText" in script
    assert "const terms=[" in script
    assert "current_date_observation_utc" in script
    assert "company_bids_submitted:0" in script
    assert "--user-data-dir=" in script
    assert "await rm(profile" in script
    assert "https://zakupki.mos.ru/newapi" not in script
    assert "submitBid" not in script
    assert "registerCompany" not in script
