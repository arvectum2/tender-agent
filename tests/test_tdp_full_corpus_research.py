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


def test_manifest_ids_ignore_case_without_claiming_missing_documents():
    sources = [doc("file-01", "notice", "<purchaseNumber>123</purchaseNumber>")]
    result = research_full_corpus(
        sources, manifest=[{"file_id": "FILE-01", "display_name": "original.xml"}],
    )
    assert result["document_count"] == 1
    assert result["unread_file_ids"] == []


def test_price_evidence_includes_notice_and_contract_instead_of_contract_repeats():
    notice = doc("first", "notice", "<maxPrice>1000000.00</maxPrice>")
    contract = doc("second", "contract_draft", ("Цена контракта и изменение цены контракта. " * 200))
    result = research_full_corpus(
        [notice, contract],
        questions=[
            ResearchQuestion(
                "price", "НМЦК и изменение цены", ("maxprice", "цена контракта", "изменение цены"),
                ("notice", "contract_draft"),
            ),
        ],
    )
    hits = result["findings"][0]["hits"]
    assert hits[0]["role"] == "notice"
    assert any(h["role"] == "contract_draft" for h in hits)
    assert "<maxPrice>1000000.00</maxPrice>" in hits[0]["quote"]


def test_multiple_published_notice_versions_are_not_silently_reconciled():
    report = research_full_corpus([
        doc("rev01", "notice", "<maxPrice>1000000</maxPrice>"),
        doc("rev02", "notice", "<maxPrice>800000</maxPrice>"),
    ])
    assert report["multiple_notices_require_revision_resolution"] is True
    assert report["source_status"] == "MULTIPLE_NOTICE_REVISIONS_REVIEW"


def test_bounded_brief_retains_cross_document_references_and_never_verifies():
    from src.modules.tender_operator_agent_demo.full_corpus_research import (
        build_research_brief,
    )

    report = research_full_corpus([
        doc("first", "notice", "<maxPrice>1000000</maxPrice>"),
        doc("second", "contract_draft", "Исключительные права передаются Заказчику."),
    ])
    brief = build_research_brief(report, max_chars=4300)
    assert len(brief["source_evidence_brief"]) <= 4300
    assert "normalized:" in brief["source_evidence_brief"]
    assert "HUMAN CHECK REQUIRED" in brief["source_evidence_brief"]
    assert brief["semantic_verification"] == "NOT_PERFORMED"
    assert brief["review_status"] == "HUMAN_REVIEW_REQUIRED"


def test_real_run_facade_indexes_all_docs_before_llm_and_keeps_sources_review_only():
    from src.modules.tender_operator_agent_demo.operator_full_corpus_runtime import (
        run_with_full_corpus_research,
    )

    state = {}
    metadata = {
        "files": [
            {"file_id": "FILE-01", "display_name": "notice.xml"},
            {"file_id": "FILE-02", "display_name": "contract.docx"},
            {"file_id": "FILE-03", "display_name": "annex.xls"},
        ],
        "limitations": [],
    }
    originals = [
        doc("file-01", "notice", "<maxPrice>1000000</maxPrice>"),
        doc("file-02", "contract_draft", "По соглашению сторон цена может меняться."),
        doc("file-03", "supporting", "Дополнительная спецификация: обслуживание."),
    ]

    def collect(_run_id, _metadata):
        return originals

    def model(*, source_research=None, **_kwargs):
        state["model_brief"] = source_research
        return {"requirements": {"technical_requirements": ["Обслуживание."]}}

    def project(*, metadata, requirements, calibrated_risks, **_kwargs):
        assert metadata["source_research"]["document_count"] == 3
        assert metadata["source_research"]["extracted_document_count"] == 3
        return {"trace": {}, "requirements": {}}

    def handler(run_id, **dependencies):
        assert run_id == "case-1"
        dependencies["_collect_documents"](run_id, metadata)
        generated = dependencies["_try_run_llm_workflow"]()
        outputs = dependencies["_build_output_payloads"](
            metadata=metadata,
            requirements=generated["requirements"],
            calibrated_risks=[],
        )
        state["outputs"] = outputs
        return outputs

    run_with_full_corpus_research(
        handler, "case-1",
        _collect_documents=collect,
        _try_run_llm_workflow=model,
        _build_output_payloads=project,
    )
    brief = state["model_brief"]
    assert brief["original_document_count"] == 3
    assert brief["review_status"] == "HUMAN_REVIEW_REQUIRED"
    assert "normalized:" in brief["source_evidence_brief"]
    assert metadata["source_research"]["unread_file_ids"] == []
    assert metadata["source_research_llm_claims"][0]["semantic_verification"] == "NOT_PERFORMED"
    assert state["outputs"]["trace"]["full_corpus_research"]["overall_decision"] == "HUMAN_REVIEW_REQUIRED"
    assert any("не правильность юридического толкования" in s for s in metadata["limitations"])


def test_extra_model_research_only_passed_to_explicitly_compatible_callable():
    from src.modules.tender_operator_agent_demo.operator_full_corpus_runtime import (
        run_with_full_corpus_research,
    )

    received = {}
    def collector(_id, _meta):
        return [doc("file1", "notice", "Срок подачи заявок указан в документации.")]

    def legacy_llm_without_new_kwarg(*, notice_text):
        received["notice_text"] = notice_text
        return {}

    def handler(run_id, **dependencies):
        metadata = {"files": []}
        dependencies["_collect_documents"](run_id, metadata)
        dependencies["_try_run_llm_workflow"](notice_text="оригинал")
        return metadata

    run_with_full_corpus_research(
        handler, "run1",
        _collect_documents=collector,
        _try_run_llm_workflow=legacy_llm_without_new_kwarg,
        _build_output_payloads=lambda **kwargs: {},
    )
    assert received["notice_text"] == "оригинал"
