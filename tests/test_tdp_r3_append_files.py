"""Source-preserving append upload validation/persistence regression tests."""
from __future__ import annotations

import ast
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.schemas import (
    TenderOperatorUploadedRunStatus,
)

EXPECTED_SHA256 = "994bc3139ad6c7ade15cf88beb37ce706b8a92bae06c2dc78ad9723054f24446"
MODULE = Path(__file__).resolve().parents[1] / "src/modules/tender_operator_agent_demo/operator_append_files.py"


def test_original_append_body_ast_remains_identical():
    f = next(n for n in ast.parse(MODULE.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == "append_files_to_demo_run")
    actual = hashlib.sha256(ast.dump(ast.Module(body=f.body, type_ignores=[]), include_attributes=False).encode()).hexdigest()
    assert actual == EXPECTED_SHA256


def _metadata():
    return {
        "run_id": "toa-run-test",
        "created_at": "2026-10-11T14:00:00+00:00",
        "status": "docs_required",
        "attachments_status": "manual_upload_required",
        "files": [], "warnings": [], "limitations": [],
    }


def test_preflight_failure_must_not_write_or_mutate(monkeypatch, tmp_path):
    data = _metadata()
    calls = []
    monkeypatch.setattr(legacy, "_load_metadata", lambda _id: data)
    monkeypatch.setattr(legacy, "_input_dir", lambda _id: tmp_path)
    def invalid(*args, **kwargs):
        calls.append("validate")
        raise HTTPException(status_code=413, detail="Batch exceeds limit")
    monkeypatch.setattr(legacy, "validate_operator_upload_batch", invalid)
    monkeypatch.setattr(legacy, "save_demo_run_metadata", lambda *_: calls.append("save"))
    monkeypatch.setattr(legacy, "append_demo_run_event", lambda *_: calls.append("event"))
    with pytest.raises(HTTPException) as error:
        legacy.append_files_to_demo_run(run_id="toa-run-test", uploads=[("oversize.pdf", "application/pdf", b"x")])
    assert error.value.status_code == 413
    assert calls == ["validate"]
    assert data["files"] == []
    assert data["status"] == "docs_required"
    assert list(tmp_path.iterdir()) == []


def test_valid_append_preserves_events_status_and_descriptor(monkeypatch, tmp_path):
    data = _metadata()
    events, stored = [], []
    monkeypatch.setattr(legacy, "_load_metadata", lambda _id: data)
    monkeypatch.setattr(legacy, "_input_dir", lambda _id: tmp_path)
    monkeypatch.setattr(legacy, "validate_operator_upload_batch", lambda *a, **k: None)
    monkeypatch.setattr(legacy, "save_demo_run_metadata", lambda rid, meta: stored.append((rid, meta.copy())))
    monkeypatch.setattr(legacy, "append_demo_run_event", lambda rid, key, *args: events.append(key))
    result = legacy.append_files_to_demo_run(
        run_id="toa-run-test", uploads=[("price.txt", "text/plain", b"Confirmed source")]
    )
    assert result.status == TenderOperatorUploadedRunStatus.READY_TO_ANALYZE
    assert result.file_count == 1
    assert data["attachments_status"] == "manual_upload_received"
    assert data["manual_upload_required"] is False
    assert (tmp_path / data["files"][0]["stored_name"]).read_bytes() == b"Confirmed source"
    assert events == ["attachment_saved", "manual_upload_received"]
    assert len(stored) == 1
    assert result.created_at == datetime(2026, 10, 11, 14, tzinfo=UTC)
