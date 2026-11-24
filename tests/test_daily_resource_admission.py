"""Synthetic-only regression for daily full-run admission; no live workflow."""
import json
import os
from datetime import UTC, datetime, timedelta

import pytest

from scripts.runtime import macmini_daily_tender as daily

NOW = datetime(2026, 11, 24, 7, 30, tzinfo=UTC)


def health(path, **fields):
    data = {
        "schema": 1,
        "status": "pass",
        "mode": "normal",
        "batch_limit": 10,
        "checked_at_utc": (NOW - timedelta(seconds=30)).isoformat(),
        "untrusted": "SECRET_SOURCE",
    }
    data.update(fields)
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    return path


def test_normal_only_when_recent_and_trusted(tmp_path):
    daily.require_full_resource_admission(health(tmp_path / "health.json"), now=NOW)


@pytest.mark.parametrize("fields", [
    {"mode": "paused", "batch_limit": 0},
    {"mode": "reduced", "batch_limit": 3},
    {"mode": "normal", "batch_limit": 3},
    {"mode": "normal", "batch_limit": True},
    {"status": "fail"},
    {"status": "HEALTHY"},
    {"schema": 2},
    {"schema": True},
    {"mode": "UNKNOWN"},
    {"checked_at_utc": (NOW - timedelta(seconds=101)).isoformat()},
    {"checked_at_utc": (NOW + timedelta(seconds=1)).isoformat()},
    {"checked_at_utc": NOW.replace(tzinfo=None).isoformat()},
    {"checked_at_utc": None},
    {"checked_at_utc": "SECRET_TIMESTAMP"},
])
def test_blocked_without_leaking_private_data(tmp_path, fields):
    p = health(tmp_path / "health.json", **fields)
    with pytest.raises(RuntimeError) as exc:
        daily.require_full_resource_admission(p, now=NOW)
    assert str(exc.value) == "Resource admission unavailable"
    assert "SECRET" not in str(exc.value)
    assert str(p) not in str(exc.value)


@pytest.mark.parametrize("raw", ['{invalid', '"valid"', '{}', '[]', "x" * 4097])
def test_malformed_and_oversized_telemetry_denied(tmp_path, raw):
    p = tmp_path / "health.json"
    p.write_text(raw)
    p.chmod(0o600)
    with pytest.raises(RuntimeError, match="unavailable"):
        daily.require_full_resource_admission(p, now=NOW)


def test_missing_and_symlink_not_trusted(tmp_path):
    with pytest.raises(OSError):
        daily.require_full_resource_admission(tmp_path / "missing.json", now=NOW)
    p = health(tmp_path / "source.json")
    alias = tmp_path / "health.json"
    alias.symlink_to(p)
    with pytest.raises(OSError):
        daily.require_full_resource_admission(alias, now=NOW)


def test_world_writable_file_denied(tmp_path):
    p = health(tmp_path / "health.json")
    p.chmod(0o666)
    with pytest.raises(RuntimeError, match="unavailable"):
        daily.require_full_resource_admission(p, now=NOW)


def test_capacity_gate_comes_before_marker_and_database(tmp_path, monkeypatch):
    p = health(tmp_path / "health.json", mode="paused", batch_limit=0)
    source_guard = daily.require_full_resource_admission
    monkeypatch.setattr(daily, "no_maintenance", lambda: None)
    monkeypatch.setattr(daily, "check_lock_paths", lambda: None)
    monkeypatch.setattr(daily, "MARKER", tmp_path / "missing_marker")
    monkeypatch.setattr(
        daily, "require_full_resource_admission",
        lambda: source_guard(p, now=NOW),
    )
    with pytest.raises(RuntimeError, match="Resource admission"):
        daily.preflight()


def test_denied_fresh_job_never_executes_and_does_not_hold_lock(
    tmp_path, monkeypatch, capsys
):
    p = health(tmp_path / "health.json", mode="paused", batch_limit=0)
    source_guard = daily.require_full_resource_admission
    monkeypatch.setattr(daily.sys, "argv", ["daily"])
    monkeypatch.setattr(daily, "LOCK_ROOT", tmp_path / "daily-locks")
    monkeypatch.setattr(daily, "no_maintenance", lambda: None)
    monkeypatch.setattr(
        daily, "require_full_resource_admission",
        lambda: source_guard(p, now=NOW),
    )
    monkeypatch.setattr(os, "execve", lambda *_: pytest.fail("unexpected execve"))
    assert daily.main() == 75
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.strip() == "DAILY_PREFLIGHT_BLOCKED RuntimeError"
    fd = daily.acquire_daily_lock()
    os.close(fd)

def test_repository_template_pin_matches_owner_installed_128_revision():
    # The canonical live launcher diff was verified under ARC 24-Nov; a
    # source-only guard must never silently downgrade a production pin.
    assert daily.SHA == "023d3670adcbf6d9ae8a318f4433615fa94b680c"
    assert daily.REVISION == "128_add_tender_async_index_receipts"
    assert daily.REVISION in daily.PROBE
    assert "127_private_review_link_corrections" not in daily.PROBE
    assert daily.RELEASE.name.endswith(daily.SHA)
