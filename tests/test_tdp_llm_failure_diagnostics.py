"""An LLM/provider exception must remain observable but never leak its message."""

from __future__ import annotations

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy


def test_controlled_llm_runtime_error_has_safe_diagnostic(monkeypatch):
    events = []
    monkeypatch.setattr(legacy, "append_demo_run_event", lambda *a: events.append(a))

    class UnavailableSettings:
        database_url = None

    monkeypatch.setattr(legacy, "get_settings", lambda: UnavailableSettings())
    assert legacy._try_run_llm_workflow(
        run_id="test-run",
        notice_text="notice",
        technical_spec_text="spec",
        contract_draft_text="draft",
        quote_paths=[],
    ) is None
    assert events == []  # intentional no-database fallback


def test_controlled_llm_bad_database_does_not_echo_sensitive_details(monkeypatch):
    events = []
    monkeypatch.setattr(legacy, "append_demo_run_event", lambda *a: events.append(a))

    class InvalidDb:
        database_url = "unknownscheme://private-secret"

    monkeypatch.setattr(legacy, "get_settings", lambda: InvalidDb())
    assert legacy._try_run_llm_workflow(
        run_id="test-run",
        notice_text="notice",
        technical_spec_text="spec",
        contract_draft_text="draft",
        quote_paths=[],
    ) is None
    assert len(events) == 1
    run_id, event, description, details = events[0]
    assert run_id == "test-run"
    assert event == "controlled_llm_runtime_failed"
    assert details["error_type"] in {"NoSuchModuleError", "ArgumentError"}
    assert "private-secret" not in str((description, details))
