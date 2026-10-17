"""Out-of-cohort synthetic revision text cannot be mistaken for legal gold."""
from __future__ import annotations

import hashlib

import pytest

from src.modules.tender_operator_agent_demo.r4_amendment_clause_diff import (
    audit_changed_material,
    normalized_source_lines,
)


def sha(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def diff(old: str, new: str):
    return audit_changed_material(
        old, new,
        previous_original_sha256=sha("unseen original A"),
        current_original_sha256=sha("unseen original B"),
    )


def test_different_binary_sha_can_have_identical_clause_text():
    text = (
        "PARAGRAPH-0001: Договор об оказании услуг\n"
        "PARAGRAPH-0002: Гарантийный срок составляет 12 месяцев.\n"
    )
    result = diff(text, text)
    assert result["textual_sequence_similarity"] == 1
    assert result["diff_blocks_by_kind"] == {}
    assert result["changed_new_text_topical_leads"] == []
    assert not result["legal_meaning_verified"]
    assert not result["independent_legal_expert_signed"]


def test_negated_to_affirmative_clause_is_a_review_signal_not_law():
    previous = "PARAGRAPH-0010: Авансирование не предусмотрено."
    current = "PARAGRAPH-0010: Авансирование предусмотрено в размере 10 процентов."
    result = diff(previous, current)
    leads = [x for x in result["changed_new_text_topical_leads"]
             if x["topic"] == "Оплата и аванс"]
    assert len(leads) == 1
    assert leads[0]["bounded_source_leads"][0]["source_locator"] == "PARAGRAPH-0010"
    assert leads[0]["bounded_source_leads"][0]["interpretation_status"].startswith("UNVERIFIED")
    assert not result["legal_meaning_verified"]


def test_table_of_contents_is_not_contractual_duty_evidence():
    old = "PDF PAGE 1\n6. Требования к защите информации ................... 73\n"
    new = "PDF PAGE 1\n6. Требования к защите информации ................... 95\n"
    result = diff(old, new)
    assert result["unmatched_current_lines"] == 1
    assert result["changed_new_text_topical_leads"] == []
    assert not result["source_text_extraction_complete"]


def test_pdf_page_and_docx_table_positions_are_attached_to_literals():
    lines = normalized_source_lines(
        "[Page 1]\nСрок исполнения контракта 3 дня.\n"
        "PARAGRAPH-0004: Подрядчик должен представить отчёт.\n"
        "TABLE-0001 ROW-0003 CELL-0002: Оплата после акта.\n"
    )
    assert [x["locator"] for x in lines] == [
        "PAGE-1 LINE-2", "PARAGRAPH-0004", "TABLE-0001 ROW-0003 CELL-0002",
    ]


def test_invalid_source_hash_or_empty_text_fails_closed():
    with pytest.raises(ValueError, match="SHA"):
        audit_changed_material("до", "после", previous_original_sha256="bad",
                               current_original_sha256=sha("okay"))
    with pytest.raises(ValueError, match="No independently"):
        diff("PARAGRAPH-0001: Оригинал", "   ")
