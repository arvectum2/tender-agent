"""Full-corpus research is source-bound, complete across files, and never legal GO."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

from src.modules.tender_operator_agent_demo.full_corpus_research import (
    ResearchQuestion,
    examine_llm_assertions,
    research_full_corpus,
)


def doc(fid: str, role: str, text: str | None):
    return SimpleNamespace(file_id=fid, role=role, display_name=f"{fid}.txt", text=text)


def test_full_corpus_search_finds_late_distant_clauses_with_exact_provenance():
    spec = ("Общие требования к сайту и структуре. " * 700) + (
        "Обязательна продажа билетов. Версия для слабовидящих должна работать."
    )
    contract = ("Юридические условия контракта. " * 1100) + (
        "По соглашению Сторон допускается изменение цены Контракта до 10 процентов."
        " Исключительные права передаются Заказчику."
    )
    docs = [doc("file-1", "technical_spec", spec), doc("file-2", "contract_draft", contract)]
    research = research_full_corpus(docs)
    assert research["document_count"] == 2
    assert research["extracted_document_count"] == 2
    assert research["source_truth_attested"] is False
    assert research["overall_decision"] == "HUMAN_REVIEW_REQUIRED"
    by_key = {entry["key"]: entry for entry in research["findings"]}
    for name, trigger in (
        ("functional_requirements", "продажа билетов"),
        ("intellectual_property", "Исключительные права передаются"),
        ("price_adjustment", "изменение цены"),
    ):
        assert by_key[name]["status"] == "SOURCE_CONTEXT_FOUND_REVIEW"
        hits = by_key[name]["hits"]
        assert any(trigger.lower() in hit["quote"].lower() for hit in hits)
        for hit in hits:
            source = next(d.text for d in docs if d.file_id == hit["file_id"])
            assert source[hit["start"]:hit["end"]] == hit["quote"]
            assert hashlib.sha256(source.encode()).hexdigest() == hit["source_sha256"]
            assert hashlib.sha256(hit["quote"].encode()).hexdigest() == hit["quote_sha256"]
            assert hit["semantic_status"] == "UNVERIFIED_CONTEXT_ONLY"


def test_incomplete_extraction_never_claims_completeness_or_absence():
    docs = [doc("file1", "notice", "Номер закупки 123."),
            doc("file2", "contract_draft", None)]
    manifest = [
        {"file_id": "file1", "display_name": "notice.xml"},
        {"file_id": "file2", "display_name": "contract.docx"},
        {"file_id": "file3", "display_name": "requirements.xls"},
    ]
    result = research_full_corpus(docs, manifest=manifest)
    assert result["document_count"] == 3
    assert result["source_status"] == "INCOMPLETE"
    assert result["unread_file_ids"] == ["file2", "file3"]
    assert result["source_truth_attested"] is False
    assert next(x for x in result["findings"] if x["key"] == "payment")["status"] == "NOT_FOUND_IN_EXTRACTED_TEXT"


def test_conflicting_sourced_fragments_are_both_visible_not_reconciled():
    one = doc("notice", "notice", "НМЦК: максимальная цена 1000000 рублей.")
    two = doc("amendment", "notice", "НМЦК: максимальная цена 1500000 рублей.")
    result = research_full_corpus(
        [one, two],
        questions=[ResearchQuestion("price", "НМЦК", ("нмцк",), ("notice",))],
    )
    hits = result["findings"][0]["hits"]
    assert {hit["file_id"] for hit in hits} == {"notice", "amendment"}
    assert result["source_truth_attested"] is False


def test_unsupported_model_assertion_stays_unverified_even_with_lexical_overlap():
    result = research_full_corpus(
        [doc("contract", "contract_draft",
             "По соглашению сторон допускается изменение цены контракта на десять процентов.")],
    )
    evaluated = examine_llm_assertions(
        result,
        ["Цена контракта не может изменяться в течение срока действия.",
         "Обязательная лицензия медицинского учреждения XYZ"],
    )
    assert len(evaluated) == 2
    assert all(row["semantic_verification"] == "NOT_PERFORMED" for row in evaluated)
    assert all(row["requires_human_review"] for row in evaluated)
    assert all(row["status"] != "VERIFIED" for row in evaluated)


def test_document_limit_and_research_budget_explicitly_fail_closed():
    huge = "документ " * 260_000
    report = research_full_corpus([doc("huge", "notice", huge)])
    assert report["documents"][0]["status"] == "OVERSIZE_UNREVIEWED"
    assert report["source_status"] == "INCOMPLETE"
    assert report["unread_file_ids"] == ["huge"]


def test_source_scanning_preserves_original_text_and_prevents_silent_rewrite():
    xml = "<purchaseNumber>0372200172326000015</purchaseNumber> " + "..." * 18
    result = research_full_corpus([doc("xml", "notice", xml)])
    candidate = next(x for x in result["findings"] if x["key"] == "identity")["hits"][0]
    assert candidate["quote"] in xml
    assert candidate["source_sha256"] == hashlib.sha256(xml.encode()).hexdigest()


def test_custom_question_can_index_new_industry_without_changing_code():
    body = ("Обычное вводное описание. " * 500) + "Обязателен мониторинг калибровки датчиков по ГОСТ."
    result = research_full_corpus(
        [doc("industrial", "supporting", body)],
        questions=[ResearchQuestion("calibration", "Калибровка", ("калибровк",))],
    )
    assert "калибровки датчиков" in result["findings"][0]["hits"][0]["quote"]
