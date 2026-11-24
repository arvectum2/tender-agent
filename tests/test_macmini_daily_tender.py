"""Read-only preflight and fail-closed daily lock checks."""
import os
import sys

import pytest

from scripts.runtime import macmini_daily_tender as daily


def test_preflight_does_not_execute(monkeypatch):
    monkeypatch.setattr(sys,"argv",["daily","--preflight"])
    monkeypatch.setattr(daily,"preflight",lambda:{"fixture":"value"})
    monkeypatch.setattr(daily,"acquire_daily_lock",lambda:pytest.fail("preflight writes lock"))
    monkeypatch.setattr(os,"execve",lambda *a:pytest.fail("preflight executed workflow"))
    assert daily.main()==0


def test_maintenance_and_legacy_lock(tmp_path,monkeypatch):
    monkeypatch.setattr(daily,"DEPLOY_LOCK",tmp_path/"deploy.lock")
    monkeypatch.setattr(daily,"LOCK_ROOT",tmp_path/"daily")
    daily.no_maintenance()
    daily.DEPLOY_LOCK.mkdir()
    with pytest.raises(RuntimeError,match="maintenance"):
        daily.no_maintenance()
    daily.DEPLOY_LOCK.rmdir()
    daily.LOCK_ROOT.mkdir()
    (daily.LOCK_ROOT/"daily-tender-run.lock").mkdir()
    with pytest.raises(RuntimeError,match="Legacy"):
        daily.no_maintenance()


def test_lock_released_on_fd_close(tmp_path,monkeypatch):
    monkeypatch.setattr(daily,"LOCK_ROOT",tmp_path/"daily")
    daily.LOCK_ROOT.mkdir(mode=0o755)
    fd=daily.acquire_daily_lock()
    try:
        with pytest.raises(BlockingIOError):
            daily.acquire_daily_lock()
    finally:
        os.close(fd)
    os.close(daily.acquire_daily_lock())


def test_dirty_or_stale_release_rejected(tmp_path,monkeypatch):
    import json
    from pathlib import Path
    home=tmp_path/"base";home.mkdir()
    marker=home/"marker.json"
    marker.write_text(json.dumps({"commit":"f"*40}));marker.chmod(0o600)
    monkeypatch.setattr(daily,"MARKER",marker)
    monkeypatch.setattr(daily,"no_maintenance",lambda:None)
    monkeypatch.setattr(daily,"private_file",lambda _:None)
    monkeypatch.setattr(daily,"check_lock_paths",lambda:None)
    monkeypatch.setattr(daily,"require_full_resource_admission",lambda:None)
    monkeypatch.setattr(daily,"RELEASE",Path(home))
    with pytest.raises(RuntimeError,match="pin"):
        daily.preflight()


def test_env_file_requires_private_mode(tmp_path):
    p=tmp_path/"runtime.env";p.write_text("FIXTURE=1");p.chmod(0o644)
    with pytest.raises(ValueError):
        daily.private_file(p)


def test_failure_never_runs_workflow(monkeypatch):
    monkeypatch.setattr(sys,"argv",["daily","--preflight"])
    def fail():
        raise RuntimeError("fixture mismatch")
    monkeypatch.setattr(daily,"preflight",fail)
    monkeypatch.setattr(os,"execve",lambda *a:pytest.fail("unexpected workflow"))
    assert daily.main()==75
