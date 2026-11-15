"""Source-capture gap audit never writes; checks all real persisted run IDs."""
from __future__ import annotations

from scripts.procurement_llm.audit_learning_capture import audit
from src.modules.procurement_learning_corpus.service import (
    append_candidate,
    make_analysis_candidate,
)
from src.tender_research.rag.history_service import record_analysis_run


def test_analysis_capture_completeness_read_only_for_missing_and_recovered(session, monkeypatch):
    monkeypatch.setenv("TENDER_LEARNING_CAPTURE_ENABLED", "0")
    run = record_analysis_run(
        session, registry_number="0163200000326005243",
        status="completed", used_llm=True, llm_model="gemma4", source="local",
    )
    before = audit(session)
    assert before["saved_tender_agent_analysis_runs"] == 1
    assert before["saved_runs_missing_candidate_capture"] == 1
    assert before["existing_learning_observation_total"] == 0
    assert before["all_saved_analysis_runs_have_learning_capture"] is False
    assert before["database_mutations"] == 0
    assert before["future_external_chatgpt_coverage_verified"] is False
    assert before["human_training_gold_created"] is False

    assert append_candidate(session, make_analysis_candidate(run))
    session.commit()
    after = audit(session)
    assert after["saved_tender_agent_analysis_runs"] == 1
    assert after["saved_runs_missing_candidate_capture"] == 0
    assert after["saved_runs_with_candidate_capture"] == 1
    assert after["existing_learning_observation_total"] == 1
    assert after["all_saved_analysis_runs_have_learning_capture"] is True
    assert after["unexpected_training_status_count"] == 0
