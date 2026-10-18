"""Only owner-private prewrite PostgreSQL backups and durable run receipts."""
from __future__ import annotations

import hashlib
import json
import stat
from datetime import UTC, datetime

import pytest

from scripts.procurement_llm import source_pipeline_runtime as r


def root(tmp_path):
    p = tmp_path / "owner"
    p.mkdir(mode=0o700)
    p.chmod(0o700)
    return p


def report():
    return {
        "schema": "arvectum_daily_source_pipeline_receipt_v1",
        "observed_at_utc": "2026-10-18T20:10:00+00:00",
        "new_learning_source_observations": 2,
        "pending_actual_tender_agent_analysis": ["workspace:19099"],
        "training_gold_created": False,
    }


def test_single_runner_creates_private_lock_and_refuses_nested_run(tmp_path):
    p = root(tmp_path)
    with (
        r.single_runner(p),
        pytest.raises(r.PipelineRuntimeError, match="still active"),
        r.single_runner(p),
    ):
        pass
    lock = p / "intake-runs" / "unified-source-pipeline.lock"
    assert lock.stat().st_mode & 0o077 == 0
    with r.single_runner(p):
        pass


def test_backup_full_postgresql_catalogue_sha_private_and_immutable(tmp_path, monkeypatch):
    p = root(tmp_path)
    archive = b"PGDMP" + (b"X" * 4096)
    def fake_exec(command, *, input_bytes=None):
        if "pg_dump" in command:
            assert "-d" in command and "arvectum" in command
            return archive
        assert "pg_restore" in command
        assert input_bytes == archive
        return (b"TABLE public procurement_learning_observations\n"
                b"TABLE DATA public procurement_learning_observations\n")
    monkeypatch.setattr(r, "_run_docker", fake_exec)
    evidence = r.fresh_pg_backup(p)
    assert evidence["backed_up_existing_database"] == "arvectum"
    assert evidence["restore_catalogue_verified"] is True
    assert evidence["restored_live_database"] is False
    path = __import__("pathlib").Path(evidence["private_backup_path"])
    assert path.read_bytes() == archive
    assert evidence["sha256"] == hashlib.sha256(archive).hexdigest()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_backup_missing_learning_table_fails_closed_before_file(tmp_path, monkeypatch):
    p = root(tmp_path)
    def bad(command, *, input_bytes=None):
        return (b"PGDMP" + b"X" * 3000) if "pg_dump" in command else b"TABLE not-our-table"
    monkeypatch.setattr(r, "_run_docker", bad)
    with pytest.raises(r.PipelineRuntimeError, match="catalogue"):
        r.fresh_pg_backup(p)
    assert not list((p / "backups").glob("*.dump"))


def test_owner_private_receipt_is_reproducible_and_not_raw_chat(tmp_path):
    p = root(tmp_path)
    path = r.save_private_receipt(report(), p)
    assert path.is_file()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text()) == report()
    assert "workspace:19099" in path.read_text()
    assert path.name.startswith("source-intake-")


def test_private_receipt_may_not_copy_eis_query_tokens(tmp_path):
    p = root(tmp_path)
    unsafe = report()
    unsafe["original_download_url"] = "docRequestUid=abc"
    with pytest.raises(r.PipelineRuntimeError):
        r.save_private_receipt(unsafe, p)
    assert not list((p / "intake-runs").glob("*.json"))


def test_receipt_unknown_schema_and_untrusted_root_rejected(tmp_path):
    p = root(tmp_path)
    with pytest.raises(r.PipelineRuntimeError):
        r.save_private_receipt({"schema": "unknown"}, p)
    link = tmp_path / "indirect"
    link.symlink_to(p, target_is_directory=True)
    with pytest.raises(r.PipelineRuntimeError), r.single_runner(link):
        pass


def test_receipt_is_not_fake_analysis(monkeypatch):
    result = report()
    assert result["training_gold_created"] is False
    assert datetime.fromisoformat(result["observed_at_utc"]).tzinfo == UTC


def test_macmini_six_hour_launchd_template_is_not_self_activated():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    template = (
        root / "scripts/runtime/com.arvectum.source-intake.plist.template"
    ).read_text(encoding="utf8")
    runner = (
        root / "scripts/runtime/run_source_intake.sh"
    ).read_text(encoding="utf8")
    assert "<key>StartInterval</key><integer>21600</integer>" in template
    assert "<key>RunAtLoad</key><false/>" in template
    assert "<key>KeepAlive</key><false/>" in template
    assert 'TENDER_SOURCE_INTAKE_APPLY:-0' in runner
    assert 'args=(--apply --confirm-database arvectum)' in runner
    assert "scripts.procurement_llm.unified_source_pipeline" in runner
    assert "TENDER_QUEUE_ANALYZE_APPLY:-0" in runner
    assert "scripts.procurement_llm.analysis_queue_worker" in runner
    assert "--max-actual 1" in runner
    assert "TENDER_QUEUE_LLM_MODEL" in runner
