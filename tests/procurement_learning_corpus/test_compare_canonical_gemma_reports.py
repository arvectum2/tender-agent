"""Exact ten-section same-model comparison, independent of tender result."""
import pytest

from scripts.procurement_llm.compare_canonical_gemma_reports import (
    MODEL,
    NUMBER,
    compare,
    evaluate_report,
)

IDS = [
    "notice_info", "subject", "customer_requirements",
    "application_composition", "evaluation_criteria",
    "contract_terms", "documentation_requirements",
    "restrictions_benefits", "deadlines", "documents_summary",
]


def sample(*, nmck: str, extra: str = "", source_number: str = NUMBER) -> str:
    header = f"# Анализ закупки {NUMBER}\n\n**LLM:** да ({MODEL})\n"
    result = []
    for section in IDS:
        body = (
            f"Сведения: {nmck} {extra}, chunk_id=src-1111111111111111, "
            f"registry_number={source_number}"
            if section == "subject" else
            f"Сведения извещения, chunk_id=src-2222222222222222, "
            f"registry_number={NUMBER}"
        )
        result.append(f"## {section}. Название\n\n{body}\n")
    return header + "\n---\n" + "\n".join(result)


def test_canonical_report_verifies_exact_section_structure_and_model():
    result = evaluate_report(sample(nmck="НМЦК 497 178,33 ₽"))
    assert result["section_ids"] == IDS
    assert result["lexical_hints"]["real_nmck_497178_33"] is True
    assert result["wrong_15m_as_nmck_text_flag"] is False
    assert result["malformed_cited_registry_numbers"] == []


def test_wrong_registry_never_counted_as_verified_fact():
    result = evaluate_report(sample(nmck="НМЦК 15 000 000 руб.",
                                    source_number="01632000003260005243"))
    assert result["wrong_15m_as_nmck_text_flag"]
    assert result["malformed_cited_registry_numbers_count"] == 1


def test_same_model_ten_sections_compares_presence_not_gold():
    old = sample(nmck="НМЦК 15 000 000 руб.")
    new = sample(nmck="НМЦК 497 178,33 руб.", extra="1С-Битрикс и адаптивность")
    result = compare(old, new)
    assert result["baseline"]["wrong_15m_as_nmck_text_flag"]
    assert not result["enhanced"]["wrong_15m_as_nmck_text_flag"]
    assert "real_nmck_497178_33" in result["newly_mentioned_clues"]
    assert result["strictly_not_gold"] is True


def test_rejects_different_model_or_other_tender():
    original = sample(nmck="497 178,33")
    with pytest.raises(ValueError, match="not the pinned"):
        evaluate_report(original.replace(NUMBER, "0163200000326005244", 1))
    with pytest.raises(ValueError, match="model differs"):
        evaluate_report(original.replace(MODEL, "other-model"))


def test_rejects_duplicate_or_missing_sections():
    raw = sample(nmck="497 178,33")
    with pytest.raises(ValueError, match="duplicate section heading"):
        evaluate_report(raw.replace("## deadlines.", "## subject."))
    with pytest.raises(ValueError, match="same ten"):
        evaluate_report(raw.replace("## documents_summary.", "### documents_summary."))



def test_retrieval_only_source_text_is_never_credited_as_model_answer():
    raw = sample(nmck="НМЦК 497 178,33 руб.")
    raw = raw.replace(
        "Сведения: НМЦК 497 178,33 руб.",
        "Релевантные фрагменты из документов:\n[Фрагмент 1] "
        "НМЦК 497 178,33 руб.",
    )
    result = evaluate_report(raw)
    assert result["retrieval_fallback_section_ids"] == ["subject"]
    assert result["accepted_model_sections"] == 9
    assert result["lexical_hints"]["real_nmck_497178_33"] is False
