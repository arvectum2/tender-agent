"""Contract: a running Gemma / Data Platform must not masquerade as LLM analysis."""

from __future__ import annotations

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy


def test_fallback_provenance_never_promotes_local_health_to_model_execution(
    client, monkeypatch, tmp_path
):
    from tests.test_tender_operator_agent_upload_demo import (
        _sample_upload_payload,
        _set_runs_root,
    )
    _set_runs_root(monkeypatch, tmp_path)
    monkeypatch.setattr(legacy, "_try_run_llm_workflow", lambda **kwargs: None)
    data, files = _sample_upload_payload(include_quote=False)
    created = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    assert created.status_code == 200
    rid = created.json()["run_id"]
    processed = client.post(f"/api/demo/tender-agent/runs/{rid}/analyze")
    assert processed.status_code == 200
    result = client.get(f"/api/demo/tender-agent/runs/{rid}").json()
    assert result["analysis_mode"] == "fallback_deterministic_adapter"
    assert any("Полный LLM-анализ документов не выполнялся" in x for x in result["limitations"])
    metadata = legacy._load_metadata(rid)
    assert metadata["ai_runtime_provenance"]["llm_invoked"] is False
    assert metadata["ai_runtime_provenance"]["llm_calls_count"] == 0
    assert metadata["ai_runtime_provenance"]["fallback_reason"] in (
        "configured_stub_provider",
        "controlled_llm_workflow_unavailable",
    )
