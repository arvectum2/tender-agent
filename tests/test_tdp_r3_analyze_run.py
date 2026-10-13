"""AST-preserving operator analysis orchestration regression."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy

ORIGINAL_AST_SHA256 = "2f26f194751ee5453a85e74c3a3f92a53c58b0218253b766452dfe2428f15fdc"
MODULE = Path(__file__).resolve().parents[1] / "src/modules/tender_operator_agent_demo/operator_analyze_run.py"


def test_original_analysis_body_ast_identical():
    f = next(n for n in ast.parse(MODULE.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == "analyze_uploaded_demo_run")
    current = hashlib.sha256(ast.dump(ast.Module(body=f.body, type_ignores=[]), include_attributes=False).encode()).hexdigest()
    assert current == ORIGINAL_AST_SHA256


def test_missing_source_documents_blocks_before_any_inference(monkeypatch):
    metadata = {"run_id": "toa-run-test", "status": "docs_required", "files": [],
                "warnings": [], "limitations": []}
    events, saved = [], []
    monkeypatch.setattr(legacy, "_load_metadata", lambda _rid: metadata)
    monkeypatch.setattr(legacy, "_save_metadata", lambda rid, value: saved.append(value.copy()))
    monkeypatch.setattr(legacy, "append_demo_run_event", lambda rid, event, *args: events.append(event))
    monkeypatch.setattr(legacy, "_runtime_ai_provenance", lambda: pytest.fail("no model called"))
    monkeypatch.setattr(legacy, "_collect_documents", lambda *a: pytest.fail("no doc reads"))
    with pytest.raises(HTTPException) as error:
        legacy.analyze_uploaded_demo_run("toa-run-test")
    assert error.value.status_code == 409
    assert metadata["status"] == "docs_required"
    assert metadata["analysis_status"] == "blocked"
    assert len(saved) == 1
    assert events == ["analysis_blocked"]
