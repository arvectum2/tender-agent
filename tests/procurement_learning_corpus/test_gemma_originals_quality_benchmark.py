"""Offline regression for the real original-source Gemma 12B comparison path."""
from __future__ import annotations

import pytest

from scripts.procurement_llm import gemma_originals_quality_benchmark as b
from src.tender_research.rag.search_types import RagSearchHit


def hit(doc: str, text: str, n: int = 0) -> RagSearchHit:
    return b._hit(text, file_name=doc, blob_sha="a"*64, index=n)


def test_full_source_chunking_never_discards_original_text():
    paragraphs=[
        "Условие оказания услуг и гарантийные обязательства",
        "а"*4000,
        "Период приемки с 08.12.2026 и обеспечением исполнения",
    ]
    chunks=b._chunks("\n".join(paragraphs))
    assert len(chunks)>2
    assert "".join(x.replace("\n","") for x in chunks).replace(" ","").count("а")>=4000
    assert any("08.12.2026" in x for x in chunks)


def test_originals_selection_keeps_xml_nmc_and_relevant_contract():
    cases=[
        hit("XML ЕИС v2: подтверждённые поля/ТЗ (производный)",
            "НМЦК РУБ — сумма контракта, НЕ лимит квалификационного опыта: 497178.33"
            "\nОкончание приёма заявок: 2026-10-30T11:00:00+03:00",0),
        hit("Проект государственного контракта.docx",
            "Оказание услуг не позднее 08.12.2026. Гарантия 12 месяцев.",1),
        hit("Критерии оценки заявок и порядок рассмотрения.docx",
            "Квалификация 70%; цена контракта 30%; 15000000 ₽ только предел выполненных договоров",2),
    ]
    for section in ["subject","deadlines","contract_terms","evaluation_criteria"]:
        selected=b.selection(cases,section)
        assert selected and any("497178.33" in x.text for x in selected)
    assert b.QUALITY_GEMMA_LLAMA_MODEL if hasattr(b,"QUALITY_GEMMA_LLAMA_MODEL") else b.MODEL
    assert "8081" in b.SERVER


def test_untrusted_source_without_xml_original_rejected():
    with pytest.raises(RuntimeError,match="XML"):
        b.selection([hit("Проект государственного контракта.docx",
                         "01.10.2026 497178.33")],"subject")


def test_source_partition_cannot_cross_original_number():
    model_hit=hit("XML ЕИС v2: подтверждённые поля/ТЗ (производный)",
                  "НМЦК РУБ: 497178.33")
    assert model_hit.registry_number == b.NUMBER
    assert model_hit.chunk_id.startswith("src-")
    assert len(model_hit.chunk_id) == 20
    assert b.ARCHIVE_SHA.startswith("4cec")


def test_quality_benchmark_preserves_all_eleven_sections():
    assert len(b.SECTIONS)==11
    assert [x["id"] for x in b.SECTIONS[:10]] == [
        "notice_info","subject","customer_requirements",
        "application_composition","evaluation_criteria","contract_terms",
        "documentation_requirements","restrictions_benefits",
        "deadlines","documents_summary",
    ]
    assert b.SECTIONS[10]["id"]=="technical_scope"
    assert b.MAX_CHARS_PER_SECTION>=20000


@pytest.mark.parametrize("invalid",["notice_info_unknown","legal_bid_go","hello"])
def test_unknown_category_has_no_fake_retrieval(invalid):
    with pytest.raises(KeyError):
        b.selection([hit("XML ЕИС v2: подтверждённые поля/ТЗ (производный)",
                         "НМЦК РУБ: 497178.33")],invalid)


def test_short_citation_hash_stable_per_original_span():
    first=hit("Official EIS XML","НМЦК 497178.33",0)
    same=hit("Official EIS XML","НМЦК 497178.33",0)
    changed=hit("Official EIS XML","НМЦК 497178.34",0)
    assert first.chunk_id==same.chunk_id
    assert first.chunk_id!=changed.chunk_id
    assert len(first.chunk_id) == 20


def test_short_source_identifiers_pass_explicit_citation_guard():
    from src.tender_research.rag.llm import _validate_source_bound_completion
    item=hit("XML ЕИС","НМЦК 497178.33",0)
    answer=f"НМЦК 497178.33, источник chunk_id={item.chunk_id}"
    response={"choices":[{"finish_reason":"stop"}]}
    assert _validate_source_bound_completion(response,answer,[item]) is None
    assert _validate_source_bound_completion(
        response,"НМЦК 497178.33; источник chunk_id=src-faked00000000000",[item]
    ) is not None
