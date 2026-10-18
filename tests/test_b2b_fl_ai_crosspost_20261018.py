"""Source-bound FL original AI business jobs; confirmed crosspost is not new."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.acceptance.audit_fl_original_ai_crosspost_20261018 import (
    CROSSPOST_WS,
    FL_ORIGINALS,
    INDEX,
    SOURCE_MATCH,
    _allowed,
    _original_url,
    audit_crosspost,
    audit_fl_card,
    list_verified_originals,
)

RECEIPT = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "docs/roadmap/b2b_fl_original_ai_crosspost_2026-10-18.json"
    ).read_text(encoding="utf-8")
)


def _fl(number: str, *, without: str | None = None) -> bytes:
    _, state, anchors = FL_ORIGINALS[number]
    kind = "Ссылка на вакансию" if state == "VACANCY_NOT_SUPPLIER_TENDER" else "Ссылка на заказ"
    requirements = " ".join(anchors)
    if without:
        requirements = requirements.replace(without, "REDACTED")
    return (
        "<html><body>" + "source " * 210
        + "Откликнуться " + kind + " " + requirements
        + "</body></html>"
    ).encode("utf-8")


def _shared(*, without: str | None = None) -> bytes:
    s = " ".join(SOURCE_MATCH)
    if without:
        s = s.replace(without, "REDACTED")
    return ("<html><body>" + "source " * 250 + s + "</body></html>").encode("utf-8")


def test_source_restricted_to_exact_6_fl_project_urls_workspace_crosspost_and_category():
    assert _allowed(INDEX)
    assert _allowed(CROSSPOST_WS)
    assert len(FL_ORIGINALS) == 6
    for id_ in FL_ORIGINALS:
        assert _allowed(_original_url(id_))
    for invalid in (
        "https://www.fl.ru/projects/5525297/",
        "https://www.fl.ru/projects/5525297/any.html",
        "https://www.fl.ru/projects/5525297/any.html?file=id",
        "https://www.fl.ru/projects/5525297/any.html#offer",
        "http://www.fl.ru/projects/5525297/any.html",
        "https://workspace.ru/advertising/",
        "https://www.fl.ru@evil.example/projects/5525297/any.html",
    ):
        assert not _allowed(invalid)


def test_original_ai_card_requires_source_anchors_and_does_not_infer_free_or_company():
    r = audit_fl_card("5525426", _fl("5525426"))
    assert r["source_classification"] == "SOURCE_IT_CUSTOMER_TASK_SCOPE_UNSPECIFIED"
    assert r["is_original_free_for_all_reply_confirmed"] is False
    assert r["is_verified_buyer_russian_llc"] is False
    assert r["is_company_account_contract_accepted"] is False
    assert r["is_current_authenticated_reply_open_confirmed"] is False
    assert r["is_new_unique_b2b_customer_contract"] is False
    assert r["fl_html_customer_tz_attachment_href_state"] == (
        "NO_PUBLIC_TZ_ATTACHMENT_HREF_IN_RETRIEVED_HTML"
    )
    with pytest.raises(ValueError, match="obligation changed"):
        audit_fl_card("5525426", _fl("5525426", without="Бюджет: 50 000 ₽"))


def test_hiring_and_personal_pc_tasks_cannot_become_company_procurement():
    assert audit_fl_card("5525421", _fl("5525421"))["source_classification"] == (
        "VACANCY_NOT_SUPPLIER_TENDER"
    )
    assert audit_fl_card("5524917", _fl("5524917"))["source_classification"] == (
        "PERSONAL_PC_CLIENT_LEGAL_B2B_UNVERIFIED"
    )


def test_exact_six_source_anchor_crosspost_is_not_independent_purchase():
    r = audit_crosspost(_shared(), _shared())
    assert r["fl_original_id"] == "5525297"
    assert r["workspace_original_id"] == "19030"
    assert r["deduplication_state"] == (
        "HIGH_CONFIDENCE_SAME_SCOPE_CROSSPOST_NOT_NEW_INDEPENDENT_LEAD"
    )
    assert len(r["shared_distinct_original_scope_fragments"]) == 6
    assert r["legal_buyer_inn_confirmed_same"] is False
    assert r["full_tz_pdf_original_downloaded"] is False
    assert r["independent_buyer_verification_required"] is True
    with pytest.raises(ValueError, match="cross-platform"):
        audit_crosspost(_shared(without="50 SKU"), _shared())


def test_original_category_membership_not_just_any_html_references():
    index_html = (
        "<html><body>" + "source " * 250
        + "".join(
            f'<a href="{_original_url(id_)}">Original task</a>'
            for id_ in FL_ORIGINALS
        )
        + "</body></html>"
    ).encode("utf-8")
    assert list_verified_originals(index_html)["explicit_exact_card_urls_verified"] == 6
    modified = index_html.replace(_original_url("5525297").encode(), b"https://evil.example/")
    with pytest.raises(ValueError, match="not in category"):
        list_verified_originals(modified)


def test_source_receipt_has_no_fake_legal_go_or_double_count():
    r = RECEIPT
    assert r["schema_version"] == "ta-b2b-first-party-fl-ai-crosspost-2026-10-18-v1"
    assert r["reviewed_fl_original_card_count"] == 6
    assert r["distinct_fl_customer_it_descriptions_requiring_legal_review"] == 3
    assert r["crossposted_existing_workspace19030_count_not_new"] == 1
    assert r["vacancy_and_personal_scope_not_counted_as_b2b"] == 2
    assert r["verified_company_open_free_replies"] == 0
    assert r["verified_legal_company_eligible_contracts"] == 0
    assert r["user_company_paid_or_sent_actions"] == 0
    assert len(r["cards"]) == 6
    assert len({row["id"] for row in r["cards"]}) == 6
    assert all(len(row["original_source_html_sha256"]) == 64 for row in r["cards"])
    for row in r["cards"]:
        assert row["is_original_free_for_all_reply_confirmed"] is False
        assert row["is_company_account_contract_accepted"] is False
        assert row["is_new_unique_b2b_customer_contract"] is False
        assert row["paid_action"] is False
        assert row["bid_or_reply_sent"] is False
    duplicate = next(x for x in r["cards"] if x["id"] == "5525297")
    assert duplicate["source_classification"] == "DUPLICATE_BUSINESS_SCOPE_WORKSPACE19030"
    assert duplicate["fl_html_customer_tz_attachment_href_state"] == (
        "NO_PUBLIC_TZ_ATTACHMENT_HREF_IN_RETRIEVED_HTML"
    )
    assert len(r["crosspost"]["workspace_original_html_sha256"]) == 64
