"""A sourced quality rerun must not impersonate original source completion."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from scripts.procurement_llm import source_quality_rerun as q


def test_source_identity_is_pinned():
    assert q.NUMBER == "0163200000326005243"
    assert q.SOURCE == "source_quality_rerun"
    assert q.SOURCE != "source_queue"


def test_existing_quality_run_is_idempotent(monkeypatch):
    monkeypatch.setattr(q, "source_for_case", lambda session,number: object())
    monkeypatch.setattr(q, "existing_rerun", lambda session,number: True)
    session=MagicMock()
    result=q.run_quality_once(session)
    assert result["status"] == "already_recorded_no_duplicate_run"
    assert result["new_model_calls"] == 0
    session.commit.assert_not_called()


def test_unready_index_must_not_run_model(monkeypatch):
    monkeypatch.setattr(q, "source_for_case", lambda session,number: object())
    monkeypatch.setattr(q, "existing_rerun", lambda session,number: False)
    monkeypatch.setattr(q, "readiness", lambda *a,**k:
                        {"ready_for_actual_llm": False, "blockers": ["data_platform_index_incomplete"]})
    monkeypatch.setattr(q,"analyze_tender",lambda *a,**k:
                        pytest.fail("unready RAG index cannot be used by LLM"))
    with pytest.raises(q.WorkerGateError,match="data_platform_index_incomplete"):
        q.run_quality_once(MagicMock())


def test_genuine_rerun_has_distinct_history_and_zero_gold(tmp_path, monkeypatch):
    import json
    from hashlib import sha256

    reports=tmp_path/"rag"/"reports"
    reports.mkdir(parents=True)
    report=reports/"quality-run.md"
    report.write_text("Verified archived original source, no external legal claim.")
    source=SimpleNamespace(observation_id="a"*64, original_sha256="b"*64)
    monkeypatch.setattr(q,"source_for_case",lambda session,number:source)
    monkeypatch.setattr(q,"existing_rerun",lambda session,number:False)
    monkeypatch.setattr(q,"readiness",lambda *a,**kw:{
        "ready_for_actual_llm":True,"blockers":[],
    })
    section=SimpleNamespace(status="completed",sources=[SimpleNamespace(chunk_id="source-sha")])
    def model(*args,**kw):
        assert kw["history_source"]==q.SOURCE
        assert kw["analysis_mode"]=="detailed"
        return SimpleNamespace(
            run_id="new-real-run",report_path=str(report),sections=[section],
            sections_count=1,duration_seconds=19.2,llm_calls_count=1,status="completed",
        )
    monkeypatch.setattr(q,"analyze_tender",model)
    monkeypatch.setattr(q,"load_config",lambda:SimpleNamespace(data_dir=str(tmp_path)))
    run=SimpleNamespace(id="new-real-run",registry_number=q.NUMBER,source=q.SOURCE,
                        used_llm=True,llm_model=q.QUALITY_GEMMA_LLAMA_MODEL,
                        metadata_json="{}")
    session=MagicMock()
    session.scalars.return_value.all.return_value=[]
    session.get.return_value=run
    output=q.run_quality_once(session)
    assert output["status"]=="actual_quality_history_recorded"
    assert output["human_gold"] is False
    assert output["report_sha256"]==sha256(report.read_bytes()).hexdigest()
    assert report.stat().st_mode & 0o777==0o600
    metadata=json.loads(run.metadata_json)["archival_quality_recheck"]
    assert metadata["source_original_zip_sha256"]=="b"*64
    assert metadata["second_source_completion"] is False
    assert metadata["training_gold"] is False
    session.commit.assert_called_once()
