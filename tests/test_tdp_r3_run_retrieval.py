"""Regression checks for saved procurement run projection."""
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

EXPECTED_BODY_SHA256 = "a1fd15f9a79f5ec079fd6d4c29778ac0c9714acaa0addebabc97e8da51787bd6"
EXTRACTED_MODULE = (
    Path(__file__).resolve().parents[1]
    / "src/modules/tender_operator_agent_demo/operator_run_retrieval.py"
)


def _metadata():
    return {
        "run_id": "toa-run-test",
        "created_at": "2026-10-11T12:00:00+00:00",
        "mode": "manual",
        "tender_title": "Загрузка документов",
        "tender_category": "goods",
        "customer_name": "Заказчик",
        "status": "needs_review",
        "files": [],
    }


def _patch_readonly(monkeypatch, tmp_path, *, metadata=None):
    monkeypatch.setattr(legacy, "_load_metadata", lambda run_id: metadata or _metadata())
    monkeypatch.setattr(legacy, "_output_dir", lambda run_id: tmp_path)
    monkeypatch.setattr(legacy, "_report_html_path", lambda run_id: tmp_path / "report.html")
    monkeypatch.setattr(legacy, "_ensure_procurement_blocked_report_html", lambda run_id: tmp_path / "missing.html")
    monkeypatch.setattr(legacy, "load_demo_run_events", lambda run_id: [])


def test_projected_body_matches_original_ast():
    tree = ast.parse(EXTRACTED_MODULE.read_text())
    fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "project_uploaded_run")
    digest = hashlib.sha256(
        ast.dump(ast.Module(body=fn.body, type_ignores=[]), include_attributes=False).encode()
    ).hexdigest()
    assert digest == EXPECTED_BODY_SHA256


def test_absent_saved_outputs_stay_unknown_without_invented_decision(monkeypatch, tmp_path):
    _patch_readonly(monkeypatch, tmp_path)
    result = legacy.get_uploaded_demo_run("toa-run-test")
    assert result.status == TenderOperatorUploadedRunStatus.NEEDS_REVIEW
    assert result.steps == []
    assert result.final_recommendation is None
    assert result.quote_comparison is None
    assert result.economics_summary is None
    assert result.report_html_url is None
    assert result.no_platform_submission and result.no_email_sending and result.no_digital_signature
    assert result.created_at == datetime(2026, 10, 11, 12, tzinfo=UTC)


def test_saved_sections_use_original_facade_loader(monkeypatch, tmp_path):
    _patch_readonly(monkeypatch, tmp_path)
    (tmp_path / "report.json").write_text("{}")
    seen = []
    def load_report(run_id):
        seen.append(run_id)
        return {"sections": [{"title": "Проверка источников", "items": ["UNKNOWN"]}]}
    monkeypatch.setattr(legacy, "_load_report_json", load_report)
    run = legacy.get_uploaded_demo_run("toa-run-test")
    assert seen == ["toa-run-test"]
    assert len(run.steps) == 1
    assert run.steps[0].title == "Проверка источников"
    assert run.steps[0].findings == ["UNKNOWN"]


def test_missing_metadata_raises_original_not_found(monkeypatch):
    def absent(run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    monkeypatch.setattr(legacy, "_load_metadata", absent)
    with pytest.raises(HTTPException) as error:
        legacy.get_uploaded_demo_run("missing")
    assert error.value.status_code == 404
