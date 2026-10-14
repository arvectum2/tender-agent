"""Independent source modality negative audit: real quotes beat model wording."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

from src.modules.tender_operator_agent_demo.full_corpus_modality_audit import (
    audit_source_modalities,
)


def doc(file_id: str, role: str, text: str):
    return SimpleNamespace(file_id=file_id, role=role, text=text, display_name=file_id + ".txt")


_ELIGIBILITY = (
    "В соответствии с ч. 3 ст. 30 Закона №44-ФЗ установлено преимущество "
    "участникам закупок, которыми могут быть только субъекты малого предпринимательства, "
    "социально ориентированные некоммерческие организации."
)
_PRICE = (
    "3.7. Снижение цены возможно по соглашению сторон. "
    "3.8. По соглашению Сторон возможно увеличение или уменьшение "
    "объема услуг не более чем на десять процентов. При этом допускается "
    "изменение цены Контракта пропорционально изменению объема услуг. "
    "3.9. Иные условия."
)


def test_preference_claim_contradicted_by_original_only_participants():
    original = doc("notice-1", "contract_draft", _ELIGIBILITY)
    report = audit_source_modalities(
        [original],
        requirements={"qualification_requirements": [
            "Preference given to small enterprises and socially oriented non-profits (SMEs/SONKO)."
        ]},
    )
    assert report["status"] == "SOURCE_CONTRADICTIONS_REVIEW_REQUIRED"
    assert report["contradiction_count"] == 1
    item = report["findings"][0]
    assert item["status"] == "CONTRADICTED_BY_EXCLUSIVE_SOURCE"
    assert item["semantic_verification"] == "NOT_PERFORMED"
    hit = item["source_evidence"][0]
    assert hit["quote"] in _ELIGIBILITY
    assert hit["quote_sha256"] == hashlib.sha256(hit["quote"].encode()).hexdigest()
    assert hit["source_sha256"] == hashlib.sha256(_ELIGIBILITY.encode()).hexdigest()
    assert report["bid_ready"] is False


def test_proper_only_wording_not_promoted_to_verified():
    report = audit_source_modalities(
        [doc("source", "supporting", _ELIGIBILITY)],
        requirements={"qualification_requirements": ["Only SMEs and SONKO may participate."]},
    )
    assert report["contradiction_count"] == 0
    assert report["findings"][0]["status"] == "SOURCE_MODALITY_PRESENT_SEMANTICS_UNVERIFIED"
    assert report["semantic_verification"] == "NOT_PERFORMED"


def test_silent_exclusivity_omission_is_reviewed():
    report = audit_source_modalities(
        [doc("source", "notice", _ELIGIBILITY)],
        requirements={"qualification_requirements": ["SMEs and SONKO participate."]},
    )
    assert report["findings"][0]["status"] == "EXCLUSIVITY_OMITTED_REVIEW"
    assert report["bid_ready"] is False


def test_no_original_exclusivity_does_not_invent_restriction():
    report = audit_source_modalities(
        [doc("s", "notice", "Участники закупки: юридические лица и ИП.")],
        requirements={"qualification_requirements": ["Preference given to small businesses."]},
    )
    assert report["findings"] == []
    assert report["status"] == "NO_DETECTED_CONTRADICTIONS_NOT_VERIFIED"
    assert report["bid_ready"] is False


def test_contract_price_fixed_claim_contradicted_by_quoted_adjustment():
    report = audit_source_modalities(
        [doc("contract", "contract_draft", _PRICE)],
        risks=[{
            "clause": "3.8.",
            "description": "Contract price is fixed during the entire term.",
            "impact": "Supplier cannot change contract price.",
        }],
    )
    assert report["contradiction_count"] == 1
    finding = report["findings"][0]
    assert finding["status"] == "CONTRADICTED_BY_PRICE_ADJUSTMENT_CLAUSE"
    source = finding["source_evidence"][0]
    assert "изменение цены" in source["quote"]
    assert source["source_sha256"] == hashlib.sha256(_PRICE.encode()).hexdigest()


def test_price_with_no_volume_change_claim_contradicted_by_source_volume_adjustment():
    report = audit_source_modalities(
        [doc("contract", "contract_draft", _PRICE)],
        risks=[{"clause": "3.8", "description": "Reduction in price without changing the volume of services"}],
    )
    assert report["findings"][0]["status"] == "CONTRADICTED_BY_SCOPE_ADJUSTMENT_CLAUSE"


def test_correct_adjustability_statement_is_still_not_semantically_verified():
    report = audit_source_modalities(
        [doc("contract", "contract_draft", _PRICE)],
        risks=[{"clause": "3.8", "description": "Contract price may vary proportionally with change of scope"}],
    )
    assert report["contradiction_count"] == 0
    assert report["findings"][0]["status"] == "SOURCE_PRICE_CHANGE_PRESENT_SEMANTICS_UNVERIFIED"


def test_duplicate_versions_do_not_prove_price_contradiction():
    docs = [
        doc("old", "contract_draft", _PRICE),
        doc("new", "contract_draft", "3.8. Цена остаётся постоянной."),
    ]
    report = audit_source_modalities(
        docs, risks=[{"clause": "3.8", "description": "Fixed price"}],
    )
    assert report["contradiction_count"] == 0
    assert report["status"] == "NO_DETECTED_CONTRADICTIONS_NOT_VERIFIED"
