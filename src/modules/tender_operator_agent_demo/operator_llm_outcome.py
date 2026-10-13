"""Bounded evidence-based controlled LLM outcome classification.

Model endpoint health and deterministic extraction are not a successful LLM
analysis. Only actual validated section results can earn a PASSED status;
this module does not execute model calls or fabricate source citations.
"""

from __future__ import annotations

from typing import Any


def _classify_controlled_llm_result(llm_result: dict[str, Any]) -> dict[str, Any]:
    sections = llm_result.get("sections")
    if not isinstance(sections, dict) or not sections:
        return {
            "analysis_engine": "deterministic_with_failed_local_llm",
            "analysis_mode": "fallback_deterministic_adapter",
            "event_type": "llm_analysis_validation_failed",
            "fallback_reason": "controlled_llm_validation_evidence_missing",
            "failed_sections": [],
            "llm_calls_count": 0,
        }

    failed_sections = sorted(
        section_name
        for section_name, section_result in sections.items()
        if not isinstance(section_result, dict) or section_result.get("validation_status") != "PASSED"
    )
    if not failed_sections:
        return {
            "analysis_engine": "deterministic_with_local_llm",
            "analysis_mode": llm_result.get("analysis_mode", "llm_tender_operator_provider"),
            "event_type": "llm_analysis_completed",
            "fallback_reason": None,
            "failed_sections": [],
            "llm_calls_count": len(sections),
        }

    if len(failed_sections) == len(sections):
        return {
            "analysis_engine": "deterministic_with_failed_local_llm",
            "analysis_mode": "fallback_deterministic_adapter",
            "event_type": "llm_analysis_validation_failed",
            "fallback_reason": "controlled_llm_all_sections_failed",
            "failed_sections": failed_sections,
            "llm_calls_count": len(sections),
        }

    return {
        "analysis_engine": "deterministic_with_partial_local_llm",
        "analysis_mode": llm_result.get("analysis_mode", "llm_tender_operator_provider"),
        "event_type": "llm_analysis_completed_with_warnings",
        "fallback_reason": f"controlled_llm_partial_section_failure:{','.join(failed_sections)}",
        "failed_sections": failed_sections,
        "llm_calls_count": len(sections),
    }
