"""Mechanical Gemma comparison cannot confuse generated prose with original proof."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.procurement_llm.audit_gemma_four_same_version import (
    MODEL,
    NUMBER,
    audit,
)

UUID = "11111111-2222-4333-8444-555555555555"
IDS = ("subject", "customer_requirements", "evaluation_criteria", "contract_terms")


def _record() -> dict:
    texts = {
        "subject": f"НМЦК 497 178,33 руб. Источник chunk_id={UUID}",
        "customer_requirements": f"Участник подтверждает квалификацию. Источник {UUID}",
        "evaluation_criteria": f"Цена 30%, квалификация 70%, опыт цена 80%, количество 20%. {UUID}",
        "contract_terms": f"Обеспечение исполнения 0,5% цены контракта. {UUID}",
    }
    sections = []
    for name in IDS:
        sections.append({
            "id": name, "answer": texts[name], "error": None,
            "accepted": True, "attempts": 1, "duration_seconds": 30.,
            "source_evidence": [{
                "chunk_id": UUID, "registry_number": NUMBER,
                "tender_id": "tender", "sha256_text": "a" * 64,
                "file_name": "Оригинальный документ",
            }],
        })
    return {
        "schema": "smolensk_original_eis_four_section_repair_v1",
        "mode": "source_only_local_gemma",
        "model": MODEL, "procurement_ref": NUMBER,
        "selected_section_ids": list(IDS), "sections": sections,
        "canonical_database_modified": False,
        "saved_run": False, "gold_promoted": False, "legal_bid_go": False,
    }


def test_all_mechanical_anchors_and_cited_ids_present():
    result = audit(_record())
    assert result["all_four_mechanical_acceptance"]
    assert result["all_four_citations_checked"]
    assert result["all_four_key_fact_signals"]
    assert result["training_gold"] is False
    assert result["independent_human_legal_fact_verification_done"] is False


def test_accepted_but_wrong_or_omitted_nmck_fails_the_evidence_gate():
    raw = _record()
    raw["sections"][0]["answer"] = f"НМЦК не установлена. {UUID}"
    result = audit(raw)
    assert result["all_four_guard_accepted"]
    assert not result["all_four_key_fact_signals"]
    assert not result["all_four_mechanical_acceptance"]


def test_modified_chunk_id_is_not_accepted_merely_for_being_uuid():
    raw = _record()
    raw["sections"][1]["answer"] = "Чужая ссылка 44444444-2222-4333-8444-555555555555"
    assert not audit(raw)["all_four_citations_checked"]


@pytest.mark.parametrize("field,value",[
    ("saved_run", True), ("gold_promoted", True),
    ("canonical_database_modified", True), ("legal_bid_go", True),
    ("procurement_ref", "0000000000000000000"), ("model", "Qwen-not-Gemma"),
])
def test_result_must_not_impersonate_source_or_change_database(field, value):
    raw = _record()
    raw[field] = value
    with pytest.raises(ValueError):
        audit(raw)


def test_different_section_set_or_duplicate_rejected():
    raw = deepcopy(_record())
    raw["sections"][3]["id"] = "subject"
    with pytest.raises(ValueError, match="four"):
        audit(raw)
