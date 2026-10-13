"""Original upload creation body parity and fail-closed behavior."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.schemas import (
    TenderOperatorUploadedRunStatus,
)

EXPECTED_SHA256 = "ca432164b80f10615d5056a7bfdae6129b3b3cbcc1bea315b74ffbcf3f82b999"
MODULE = Path(__file__).resolve().parents[1] / "src/modules/tender_operator_agent_demo/operator_create_run.py"


def _kwargs(**override):
    return {"tender_title": "Поставка", "tender_category": "goods", "customer_name": "Заказчик", "notes": None, "target_margin_percent": None, "logistics_reserve_percent": None,
                "risk_reserve_percent": None, "payment_delay_days": None,
                "uploads": [("source.txt", "text/plain", b"Original")]} | override


def test_original_create_body_ast_identical():
    tree = ast.parse(MODULE.read_text())
    f = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "create_uploaded_demo_run")
    sha = hashlib.sha256(ast.dump(ast.Module(body=f.body, type_ignores=[]), include_attributes=False).encode()).hexdigest()
    assert sha == EXPECTED_SHA256


def test_missing_tender_title_fails_before_batch_or_filesystem(monkeypatch):
    monkeypatch.setattr(legacy, "validate_operator_upload_batch", lambda *a, **k: pytest.fail("validation must not run"))
    monkeypatch.setattr(legacy, "ensure_demo_run_structure", lambda *a, **k: pytest.fail("must not create storage"))
    with pytest.raises(HTTPException) as error:
        legacy.create_uploaded_demo_run(**_kwargs(tender_title=" "))
    assert error.value.status_code == 400


def test_rejected_batch_never_creates_run(monkeypatch):
    calls = []
    def reject(*a, **k):
        calls.append("preflight")
        raise HTTPException(status_code=413, detail="over limit")
    monkeypatch.setattr(legacy, "validate_operator_upload_batch", reject)
    monkeypatch.setattr(legacy, "make_demo_run_id", lambda: pytest.fail("no run id before preflight"))
    monkeypatch.setattr(legacy, "ensure_demo_run_structure", lambda *a, **k: pytest.fail("no disk writes"))
    with pytest.raises(HTTPException) as error:
        legacy.create_uploaded_demo_run(**_kwargs())
    assert error.value.status_code == 413
    assert calls == ["preflight"]


def test_valid_batch_persists_exact_original_and_review_only_flags(monkeypatch, tmp_path):
    from datetime import UTC, datetime
    events, saved = [], []
    monkeypatch.setattr(legacy, "validate_operator_upload_batch", lambda *a, **k: None)
    monkeypatch.setattr(legacy, "make_demo_run_id", lambda: "toa-run-test")
    monkeypatch.setattr(legacy, "ensure_demo_run_structure", lambda *a, **k: {"input_dir": tmp_path})
    monkeypatch.setattr(legacy, "_safe_datetime", lambda: "2026-10-11T15:00:00+00:00")
    monkeypatch.setattr(legacy, "save_demo_run_metadata", lambda rid, m: saved.append(m))
    monkeypatch.setattr(legacy, "append_demo_run_event", lambda rid, name, *a: events.append(name))
    result = legacy.create_uploaded_demo_run(**_kwargs())
    assert result.status == TenderOperatorUploadedRunStatus.READY_TO_ANALYZE
    assert result.file_count == 1
    assert result.created_at == datetime(2026, 10, 11, 15, tzinfo=UTC)
    assert len(saved) == 1
    assert saved[0]["human_in_the_loop"] is True
    assert saved[0]["no_platform_submission"] is True
    assert saved[0]["no_email_sending"] is True
    assert saved[0]["no_digital_signature"] is True
    assert (tmp_path / saved[0]["files"][0]["stored_name"]).read_bytes() == b"Original"
    assert events == ["run_created"]
