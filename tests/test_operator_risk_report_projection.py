"""Contract tests for the isolated product-owned risk report boundary."""

from __future__ import annotations

import pytest

from src.modules.tender_operator_agent_demo.operator_risk_report import (
    build_operator_risk_payload,
    normalized_risk_evidence_locators,
)


def _build(risks, *, claim_bound=False):
    return build_operator_risk_payload(
        risks, claim_bound_mode=claim_bound, _translate_user_text=lambda value: str(value)
    )


def test_safe_document_and_human_readable_locator_survive():
    locator = [{"document": "  ТЗ.docx  ", "locator": "  раздел 4, стр. 7  "}]
    assert normalized_risk_evidence_locators(locator) == [
        {"document": "ТЗ.docx", "locator": "раздел 4, стр. 7"}
    ]


@pytest.mark.parametrize(
    "locator",
    [
        None,
        "страница 2",
        [None],
        [{"document": "", "locator": "стр. 2"}],
        [{"document": "ТЗ.docx", "locator": ""}],
        [{"document": "C:/Users/a/TЗ.docx", "locator": "стр. 2"}],
        [{"document": r"C:\Users\a\TЗ.docx", "locator": "стр. 2"}],
        [{"document": "ТЗ.docx", "locator": "/Volumes/ArvectumSSD/private"}],
        [{"document": "ТЗ.docx", "locator": "file:/local/source.txt"}],
        [{"document": "ТЗ.docx", "locator": "/Users/master/source.txt"}],
        [{"document": "a" * 64, "locator": "стр. 2"}],
        [{"document": "01234567-89ab-cdef-0123-456789abcdef", "locator": "стр. 2"}],
    ],
)
def test_bad_or_opaque_evidence_locators_are_hidden(locator):
    assert normalized_risk_evidence_locators(locator) == []


def test_single_bad_item_suppresses_entire_evidence_locator_group():
    supplied = [
        {"document": "ТЗ.docx", "locator": "стр. 2"},
        {"document": "../private.txt", "locator": "стр. 4"},
    ]
    assert normalized_risk_evidence_locators(supplied) == []


def test_unverified_llm_risk_stays_needs_review_not_sourced_fact():
    output = _build(
        [
            {
                "risk_id": "R-1",
                "clause": "Не подтверждено",
                "impact": "Нужно сверить",
                "mitigation": "Запросить исходный документ",
                "classification": "deal_breaker_candidate",
                "source_status": "unverified_llm",
                "category": "legal",
                "evidence_ids": "E1, E2",
                "evidence_locators": [{"document": "ТЗ.docx", "locator": "стр. 8"}],
            }
        ],
        claim_bound=True,
    )
    risk = output["risks"][0]
    assert risk["source_status"] == "unverified_llm"
    assert risk["status"] == "requires_review"
    assert risk["severity"] == "needs_review"
    assert risk["evidence_ids"] == ["E1", "E2"]
    assert risk["evidence_locators"] == [{"document": "ТЗ.docx", "locator": "стр. 8"}]


def test_classified_blocker_remains_review_candidate():
    risk = _build([{"classification": "deal_breaker_candidate"}])["risks"][0]
    assert risk["severity"] == "needs_review"
    assert risk["status"] == "blocker"
    assert risk["source_status"] == "legacy_unverified"
    assert risk["evidence_locators"] == []


def test_empty_candidate_list_respects_claim_bound_mode():
    assert _build([], claim_bound=True)["risks"] == []
    ordinary = _build([], claim_bound=False)["risks"]
    assert len(ordinary) == 1
    assert ordinary[0]["risk"] == "Недостаточно данных по договорным условиям"


def test_no_external_action_and_manual_review_retained():
    output = _build([{"clause": "Срок поставки", "classification": "market_standard_harsh_term"}])
    assert output["risks"][0]["status"] == "requires_review"
    assert output["manual_checks"] == [
        "Проверить договорные ограничения и совместимость аналогов вручную."
    ]
