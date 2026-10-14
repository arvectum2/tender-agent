"""Auditable clause pointers, not model legal truth."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

from src.modules.tender_operator_agent_demo.full_corpus_clause_review import (
    audit_model_contract_clause_references,
    index_original_numbered_clauses,
)


def document(name: str, role: str, text: str):
    return SimpleNamespace(file_id=name, display_name=name + ".txt", role=role, text=text)


def test_numbered_original_clause_points_to_exact_bytes_and_hash():
    contract = (
        "3.7. Цена указана в контракте. "
        "3.8. По соглашению Сторон возможно изменение объема услуг "
        "не более десяти процентов, с пропорциональным изменением цены. "
        "3.9. Иные бюджетные основания изменения договора."
    )
    docs = [document("contract", "contract_draft", contract)]
    found = index_original_numbered_clauses(docs)
    hit = next(item for item in found if item["clause"] == "3.8")
    assert hit["quote"].startswith("3.8. По соглашению Сторон")
    assert "пропорциональным изменением цены" in hit["quote"]
    assert contract[hit["start"]:hit["end"]] == hit["quote"]
    assert hit["source_sha256"] == hashlib.sha256(contract.encode()).hexdigest()
    assert hit["quote_sha256"] == hashlib.sha256(hit["quote"].encode()).hexdigest()
    result = audit_model_contract_clause_references(
        [{"clause": "Section 3.8 Fixed contract price (model claim)"}], docs,
    )[0]
    assert result["status"] == "CLAUSE_LOCATED_NOT_SEMANTICALLY_VERIFIED"
    assert result["semantic_verification"] == "NOT_PERFORMED"
    assert result["requires_human_review"] is True
    assert result["evidence"][0]["quote"] == hit["quote"]


def test_missing_and_unnumbered_references_are_not_fabricated():
    docs = [document("contract", "contract_draft", "2.1. Предмет контракта.")]
    result = audit_model_contract_clause_references(
        [{"clause": "Section 3.8 Price Fixed"},
         {"clause": "intellectual property obligations"}], docs,
    )
    assert [x["status"] for x in result] == [
        "CLAUSE_NOT_FOUND", "NO_NUMBERED_CLAUSE_REFERENCE",
    ]
    assert all(not x["evidence"] for x in result)


def test_multiple_contract_versions_are_ambiguous_not_silently_merged():
    result = audit_model_contract_clause_references(
        [{"clause": "3.8 Volume changes"}],
        [document("old", "contract_draft", "3.8. Изменение цены запрещено."),
         document("new", "contract_draft", "3.8. Изменение цены допускается.")],
    )
    assert len(result) == 1
    assert result[0]["status"] == "AMBIGUOUS_CLAUSE_REFERENCE"
    assert {x["file_id"] for x in result[0]["evidence"]} == {"old", "new"}
    assert result[0]["semantic_verification"] == "NOT_PERFORMED"


def test_deep_technical_clauses_and_numeric_dates_are_not_misidentified():
    doc = document("spec", "technical_spec", (
        "Дата 16.10.2026. Текст. "
        "2.2.3.6.5. Версия сайта для слабовидящих обязательна. "
        "2.2.3.6.6. Иные требования."
    ))
    result = audit_model_contract_clause_references(
        [{"clause": "Section 2.2.3.6.5 Accessibility"}], [doc],
    )[0]
    assert result["status"] == "CLAUSE_LOCATED_NOT_SEMANTICALLY_VERIFIED"
    assert "Версия сайта для слабовидящих" in result["evidence"][0]["quote"]
    indexed = index_original_numbered_clauses([doc])
    assert all(not x["clause"].startswith("16.10") for x in indexed)


def test_missing_document_text_produces_no_supported_evidence():
    docs = [document("contract", "contract_draft", "")]
    result = audit_model_contract_clause_references(
        [{"clause": "§3.8"}], docs,
    )[0]
    assert result["status"] == "CLAUSE_NOT_FOUND"
    assert result["requires_human_review"] is True
