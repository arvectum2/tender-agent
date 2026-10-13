"""Only real validated model section results can be classified as successful."""

import copy

import pytest

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_llm_outcome import (
    _classify_controlled_llm_result,
)


def test_original_facade_is_retained():
    assert legacy._classify_controlled_llm_result is _classify_controlled_llm_result


@pytest.mark.parametrize("sections", [None, {}, [], "PASSED"])
def test_missing_model_sections_always_force_explicit_fallback(sections):
    payload = _classify_controlled_llm_result({"sections": sections})
    assert payload == {
        "analysis_engine": "deterministic_with_failed_local_llm",
        "analysis_mode": "fallback_deterministic_adapter",
        "event_type": "llm_analysis_validation_failed",
        "fallback_reason": "controlled_llm_validation_evidence_missing",
        "failed_sections": [],
        "llm_calls_count": 0,
    }


def test_all_validated_sections_are_not_conflated_with_deterministic_mode():
    original = {
        "analysis_mode": "llm_tender_operator_provider",
        "sections": {
            "technical_requirements": {"validation_status": "PASSED"},
            "contract_risks": {"validation_status": "PASSED"},
        },
    }
    before = copy.deepcopy(original)
    result = _classify_controlled_llm_result(original)
    assert result == {
        "analysis_engine": "deterministic_with_local_llm",
        "analysis_mode": "llm_tender_operator_provider",
        "event_type": "llm_analysis_completed",
        "fallback_reason": None,
        "failed_sections": [],
        "llm_calls_count": 2,
    }
    assert original == before


def test_all_failed_invalid_and_non_mapping_sections_never_count_as_success():
    result = _classify_controlled_llm_result({
        "analysis_mode": "llm_unverified",
        "sections": {
            "supplier_question": {"validation_status": "FAILED"},
            "contract_risks": None,
            "technical_spec": {"validation_status": "PASS"},
        },
    })
    assert result["analysis_engine"] == "deterministic_with_failed_local_llm"
    assert result["analysis_mode"] == "fallback_deterministic_adapter"
    assert result["event_type"] == "llm_analysis_validation_failed"
    assert result["fallback_reason"] == "controlled_llm_all_sections_failed"
    assert result["failed_sections"] == [
        "contract_risks", "supplier_question", "technical_spec",
    ]
    assert result["llm_calls_count"] == 3


def test_partial_validation_is_reported_as_partial_not_complete():
    result = _classify_controlled_llm_result({
        "analysis_mode": "llm_tender_operator_provider",
        "sections": {
            "requirements": {"validation_status": "PASSED"},
            "contract_risks": {"validation_status": "FAILED"},
            "supplier_questions": {"validation_status": "UNKNOWN"},
        },
    })
    assert result["analysis_engine"] == "deterministic_with_partial_local_llm"
    assert result["analysis_mode"] == "llm_tender_operator_provider"
    assert result["event_type"] == "llm_analysis_completed_with_warnings"
    assert result["fallback_reason"] == (
        "controlled_llm_partial_section_failure:contract_risks,supplier_questions"
    )
    assert result["failed_sections"] == ["contract_risks", "supplier_questions"]
    assert result["llm_calls_count"] == 3


def test_non_passed_status_never_qualifies_as_llm_evidence():
    result = _classify_controlled_llm_result({
        "sections": {"risks": {"validation_status": None}},
    })
    assert result["analysis_engine"] == "deterministic_with_failed_local_llm"
    assert result["failed_sections"] == ["risks"]
