"""Contract tests for product-owned source-analysis trace projection."""

from __future__ import annotations

from types import SimpleNamespace

from src.modules.tender_operator_agent_demo.operator_analysis_trace import (
    build_operator_analysis_trace,
)


def _doc(file_id, name, text):
    return SimpleNamespace(file_id=file_id, display_name=name, text=text)


def _trace(*, kind="goods", docs=None, rich=None, facts=None, rows=None, warnings=None):
    docs = docs if docs is not None else [_doc("N", "Извещение.xml", "Цена 500000"), _doc("T", "ТЗ.docx", "Поставка")]
    rich = rich if rich is not None else [docs[1]]
    facts = facts if facts is not None else [SimpleNamespace(file_id="T"), SimpleNamespace(file_id="T")]
    rows = rows if rows is not None else [
        {"source_fact_id": "T:page1:1", "name": "Ноутбук"},
        {"name": "Требование для проверки"},
    ]
    seen = []

    def role(document):
        seen.append(document.file_id)
        return "notice" if document.file_id == "N" else "technical_spec"

    result = build_operator_analysis_trace(
        documents=docs,
        metadata={
            "procurement_source": "eis",
            "procurement_id": "01234567890123456789",
            "procurement_url": "https://zakupki.gov.ru/example",
            "attachments_status": "partial",
            "limitations": ["Нет подписанного проекта договора"],
        },
        preliminary_analysis={"extracted_fields": ["nmck", "customer"]},
        rich_documents=rich,
        source_facts=facts,
        requirement_rows=rows,
        procurement_kind=kind,
        rationale=["Ручная проверка обязательна"],
        output_warnings=warnings if warnings is not None else ["Нет проверенного ТКП"],
        semantic_procurement_role=role,
    )
    return result, seen


def test_goods_trace_only_counts_distinct_rich_document_with_sourced_facts():
    result, seen = _trace()
    summary = result["source_extraction_summary"]
    assert summary["documents_total"] == 2
    assert summary["text_bearing_documents"] == 2
    assert summary["rich_documents"] == 1
    assert summary["rich_documents_with_facts"] == 1
    assert summary["source_facts_extracted"] == 2
    assert summary["source_derived_requirements"] == 1
    assert summary["template_requirements"] == 1
    assert summary["semantic_roles"] == {"N": "notice", "T": "technical_spec"}
    assert seen == ["N", "T"]


def test_service_trace_never_claims_goods_source_requirement_counts():
    result, _ = _trace(kind="services", rows=[{"name": "Строка услуги", "source_fact_id": "S-1"}])
    summary = result["source_extraction_summary"]
    assert summary["source_derived_requirements"] == 0
    assert summary["template_requirements"] == 0
    assert result["procurement_context"]["attachments_status"] == "partial"


def test_source_incomplete_report_retains_human_approval_and_warnings():
    result, _ = _trace()
    assert result["limitations"] == ["Нет подписанного проекта договора", "Нет проверенного ТКП"]
    assert result["decision_factors"] == ["Ручная проверка обязательна"]
    assert "Нет подачи заявок" in result["human_control_note"]
    assert "Внешние действия отключены" in result["risk_signals"][1]
    assert result["fields_extracted"] == ["nmck", "customer"]


def test_empty_and_nontext_documents_not_counted_as_proof():
    docs = [_doc("N", "Пустое извещение.xml", ""), _doc("T", "ТЗ.docx", "")]
    result, seen = _trace(docs=docs, rich=[], facts=[], rows=[])
    summary = result["source_extraction_summary"]
    assert summary["documents_total"] == 2
    assert summary["text_bearing_documents"] == 0
    assert summary["rich_documents"] == 0
    assert summary["rich_documents_with_facts"] == 0
    assert summary["source_facts_extracted"] == 0
    assert summary["semantic_roles"] == {}
    assert seen == []


def test_source_facts_in_unrelated_document_do_not_imply_rich_document_provenance():
    docs = [_doc("N", "Извещение.xml", "Документ"), _doc("T", "ТЗ.docx", "Описание")]
    result, _ = _trace(docs=docs, rich=[docs[1]], facts=[SimpleNamespace(file_id="N")])
    assert result["source_extraction_summary"]["rich_documents_with_facts"] == 0
    assert result["source_extraction_summary"]["source_facts_extracted"] == 1
