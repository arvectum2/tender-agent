"""Strict original-detail status and deadline override filtered active listing."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.acceptance.audit_moscow_narrow_originals_20261018 import (
    ORIGINALS,
    TERMS,
    _observed_list,
    check_detail,
)

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = json.loads(
    (ROOT / "docs/roadmap/b2g_moscow_10_narrow_terms_and_two_originals_2026-10-18.json")
    .read_text("utf-8")
)
NOW = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)


def _mock_browser(number):
    o = ORIGINALS[number]
    return (
        "<html><head><title>Котировочная сессия "
        + number
        + " «Техническая процедура» на Портале поставщиков</title></head><body>"
        + "<div>Котировочная сессия " + number + " " + o["detail_status"] + "</div>"
        + "<div>" + o["title"] + "</div>"
        + "<div>Заказчик " + o["buyer"] + "</div>"
        + "<div>Даты проведения по " + o["end_msk"] + "</div>"
        + "<div>Для участия в котировочной сессии необходимо авторизоваться</div>"
        + " ".join(o["known_facts"])
        + '<a href="https://zakupki.mos.ru/newapi/api/FileStorage/Download?id=285519140">'
        + "Проект договора.docx</a>" + " source " * 2300 + "</body></html>"
    )


def _synthetic_observation():
    rows = []
    for term in TERMS:
        indexes = [
            "10321173", "10314722",
        ] if term == "техническая поддержка" else []
        rows.append({
            "term": term,
            "exact_applied_query": True,
            "public_status_gate": [19000002],
            "first_page_only": True,
            "html_public_visible_text": (
                "ОРИГИНАЛ НА САЙТЕ" if indexes else "Ничего не нашлось"
            ),
            "original_detail_links": [
                {
                    "url": f"https://zakupki.mos.ru/auction/{i}?cameFrom.to=purchase.list",
                    "label": i,
                } for i in indexes
            ],
            "current_date_observation_utc": NOW.isoformat(),
        })
    return {"state": "PUBLIC_FIRST_PARTY_NARROW_IT_SEARCH_COMPLETED", "searches": rows}


def test_ten_source_filters_have_applied_public_active_gate_and_exact_ids():
    data = _observed_list(_synthetic_observation())
    assert data["original_first_party_query_count"] == 10
    assert data["source_first_page_unique_ids"] == 2
    assert [s["term"] for s in data["queries"]] == list(TERMS)
    assert all(s["source_filter_state"] == "PUBLIC_LIST_FILTER_ACTIVE_NOT_DETAIL_VERIFIED" for s in data["queries"])


@pytest.mark.parametrize("edit", [
    lambda x: x["searches"][0].update(exact_applied_query=False),
    lambda x: x["searches"][1].update(public_status_gate=[19000004]),
    lambda x: x["searches"][2].update(first_page_only=False),
    lambda x: x["searches"][3].update(term="IT-general instead of automation"),
    lambda x: x["searches"][4].update(html_public_visible_text="unknown error"),
    lambda x: x["searches"][6]["original_detail_links"][0].update(
        url="https://thirdparty.invalid/auction/10321173"
    ),
    lambda x: x["searches"][6].update(original_detail_links=[]),
])
def test_public_wrong_queries_states_or_untrusted_links_fail_closed(edit):
    observation = _synthetic_observation()
    edit(observation)
    with pytest.raises(ValueError):
        _observed_list(observation)


def test_true_source_security_scope_is_not_custom_development_or_company_ready():
    row = check_detail("10321173", _mock_browser("10321173"), NOW)
    assert row["source_detail_public_open_and_not_expired"] is True
    assert row["original_detail_current_status"] == "Активная"
    assert row["list_and_detail_status_contradict"] is False
    assert row["original_due_at_msk"].startswith("2026-10-19T12:58:04")
    assert row["source_scope"] == "SECURITY_IMPLEMENTATION_AND_SOFTWARE_LICENSES_NOT_CUSTOM_DEV"
    assert row["is_bespoke_programming_or_software_development"] is False
    assert row["company_authorized_to_bid"] is False
    assert row["user_owner_go"] is False
    assert row["company_reply_sent"] is False
    assert row["files_downloaded"] is False
    assert "ViPNet Client 5 for Linux" in row["original_line_item_scope_proofs"]
    assert len(row["original_rendered_html_sha256"]) == 64


def test_original_failed_session_beats_actively_labelled_search_result():
    row = check_detail("10314722", _mock_browser("10314722"), NOW)
    assert row["first_party_search_list_claimed_status"] == "АКТИВНАЯ"
    assert row["original_detail_current_status"] == "Не состоялась"
    assert row["list_and_detail_status_contradict"] is True
    assert row["original_due_has_passed"] is True
    assert row["source_detail_public_open_and_not_expired"] is False
    assert row["candidate_is_supplier_sales_ready"] is False
    assert row["source_scope"] == "TERMINAL_PAST_DEADLINE_NON_IT_EXPERTISE"
    # This is a procedure with unknown quantity and different maximum price.
    assert "Максимальное значение цены контракта" in row["original_line_item_scope_proofs"]
    assert "50 000 ₽" in row["original_line_item_scope_proofs"]
    assert row["source_initial_or_unit_price_rub"] == "100.00"


def test_future_clock_never_keeps_public_detail_open_past_deadline():
    future = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    row = check_detail("10321173", _mock_browser("10321173"), future)
    assert row["original_due_has_passed"] is True
    assert row["source_detail_public_open_and_not_expired"] is False
    assert row["company_authorized_to_bid"] is False


@pytest.mark.parametrize("original,replaced", [
    ("Активная", "Не состоялась"),
    ("19.10.2026 12:58:04", "21.10.2026 18:00:00"),
    ("Secret Net Studio", "Brand X"),
    ("ViPNet Client 5 for Linux", "Some VPN"),
    ("НИЖНЕМУЛЛИНСКАЯ СРЕДНЯЯ ШКОЛА", "Другая школа"),
    ("Проект договора.docx", "Проект договора.docx"),
])
def test_original_critical_terms_or_named_docs_must_not_disappear(original, replaced):
    base = _mock_browser("10321173")
    if original == replaced:
        base = base.replace(
            "https://zakupki.mos.ru/newapi/api/FileStorage/Download?id=285519140",
            "https://thirdparty.invalid/not-a-file",
        )
    else:
        base = base.replace(original, replaced)
    with pytest.raises(ValueError):
        check_detail("10321173", base, NOW)


def test_saved_ten_term_receipt_is_deduped_and_never_company_sales_ready():
    report = RECEIPT
    assert report["schema_version"] == "ta-b2g-moscow-narrow-terms-and-original-detail-reconciliation-v1"
    assert report["official_source"] == "https://zakupki.mos.ru"
    assert report["original_first_party_query_count"] == 10
    assert report["source_first_page_unique_ids"] == 25
    assert [x["term"] for x in report["queries"]] == list(TERMS)
    assert [x["first_page_numbered_originals"] for x in report["queries"]] == [
        0, 0, 0, 0, 0, 0, 10, 10, 9, 2
    ]
    assert report["original_detail_pages_verified"] == 2
    assert report["original_active_filter_is_not_authoritative_detail_status"] is True
    assert report["narrow_first_pages_bespoke_software_development_confirmed"] == 0
    assert report["claim_no_custom_software_bids_ever_exist"] is False
    assert report["verified_current_company_bids"] == 0
    assert report["new_corporate_b2b_lead_count"] == 0
    assert report["registrations_signatures_payments_replies"] == 0
    assert report["browser_profile_persisted"] is False
    by_id = {x["id"]: x for x in report["original_detail_reconciliations"]}
    assert set(by_id) == {"10321173", "10314722"}
    assert by_id["10314722"]["list_and_detail_status_contradict"] is True
    assert by_id["10314722"]["original_due_has_passed"] is True
    assert by_id["10321173"]["source_detail_public_open_and_not_expired"] is True
    for row in report["original_detail_reconciliations"]:
        assert len(row["original_rendered_html_sha256"]) == 64
        assert row["company_authorized_to_bid"] is False
        assert row["candidate_is_supplier_sales_ready"] is False


def test_browser_script_is_real_official_ui_and_does_not_use_internal_api():
    s = (
        ROOT / "scripts/acceptance/audit_moscow_public_narrow_it_filter_20261018.mjs"
    ).read_text("utf8")
    assert "const terms=['сайт','интеграция','доработка'" in s
    assert "filterNameLike" in s
    assert "Применить" in s
    assert "stateIdIn" in s
    assert "--user-data-dir=" in s
    assert "await rm(profile" in s
    assert "company_bids_submitted:0" in s
    assert "newapi/api" not in s
    assert "submitBid" not in s
