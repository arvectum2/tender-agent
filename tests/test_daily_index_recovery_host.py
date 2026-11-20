import json
from datetime import UTC, datetime, timedelta

import pytest

from scripts.ops.daily_index_recovery_host import existing_lease, resource_limit


def test_existing_lease_no_remove_or_steal(tmp_path):
    path = tmp_path / "existing.lock"
    path.touch(mode=0o600)
    with existing_lease(path), pytest.raises(BlockingIOError), existing_lease(path):
        pytest.fail("second lease unexpectedly acquired")
    with existing_lease(path):
        assert path.exists()
    assert path.exists()
    link = tmp_path / "symlink"
    link.symlink_to(path)
    with pytest.raises(OSError), existing_lease(link):
        pytest.fail("followed symlink")


@pytest.mark.parametrize("mode,limit", [("normal", 10), ("reduced", 3), ("paused", 0)])
def test_resource_limit(tmp_path, mode, limit):
    path = tmp_path / "health.json"
    data = {
        "schema": 1,
        "status": "pass",
        "mode": mode,
        "batch_limit": limit,
        "checked_at_utc": datetime.now(UTC).isoformat(),
    }
    path.write_text(json.dumps(data))
    if limit:
        assert resource_limit(path) == limit
    else:
        with pytest.raises(RuntimeError):
            resource_limit(path)
    data["checked_at_utc"] = (datetime.now(UTC) - timedelta(seconds=101)).isoformat()
    path.write_text(json.dumps(data))
    with pytest.raises(RuntimeError):
        resource_limit(path)


def test_gate_holds_leases_and_refuses_incomplete_receipt(tmp_path, monkeypatch):
    from scripts.ops import daily_index_recovery_host as host

    runtime = tmp_path.resolve() / "runtime"
    runtime.mkdir()
    resource = tmp_path.resolve() / "resource"
    resource.mkdir()
    paths = [
        resource / "heavy-slot.lock",
        runtime / "fresh-procurement-priority.lock",
        runtime / "mutation.lock",
        runtime / "research-backup-gate.lock",
    ]
    for path in paths:
        path.touch(mode=0o600)
    monkeypatch.setattr(host, "RUNTIME", runtime)
    monkeypatch.setattr(host, "RESOURCE", resource)
    monkeypatch.setattr(host, "DEPLOY_LOCK", tmp_path / "deploy.lock")
    monkeypatch.setattr(host, "resource_limit", lambda: 3)
    from collections import namedtuple

    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(
        host.shutil,
        "disk_usage",
        lambda _: Usage(50 * 1024**3, 10 * 1024**3, 40 * 1024**3),
    )
    receipt = {
        k: "evidence"
        for k in (
            "mi_head",
            "backup_sha256",
            "restore_point",
            "restore_lsn",
            "base_manifest_sha256",
        )
    }
    with host.admit_index_batch(prewrite=lambda: receipt) as (limit, actual):
        assert (limit, actual) == (3, receipt)
        for path in paths[:3]:
            with pytest.raises(BlockingIOError), host.existing_lease(path):
                pytest.fail("required host lease not held")
    with (
        pytest.raises(RuntimeError, match="receipt"),
        host.admit_index_batch(prewrite=dict),
    ):
        pytest.fail("missing receipt admitted")
    with (
        host.existing_lease(paths[0]),
        pytest.raises(BlockingIOError),
        host.admit_index_batch(prewrite=lambda: receipt),
    ):
        pytest.fail("busy host admitted")
    for path in paths:
        with host.existing_lease(path):
            assert path.exists()


def test_analysis_compute_allows_light_writes_and_commit_fences(tmp_path, monkeypatch):
    from scripts.ops import daily_index_recovery_host as host

    runtime = tmp_path.resolve() / "runtime"
    resource = tmp_path.resolve() / "resource"
    runtime.mkdir()
    resource.mkdir()
    paths = [
        resource / "heavy-slot.lock",
        runtime / "fresh-procurement-priority.lock",
        runtime / "mutation.lock",
        runtime / "research-backup-gate.lock",
    ]
    for path in paths:
        path.touch(mode=0o600)
    monkeypatch.setattr(host, "RUNTIME", runtime)
    monkeypatch.setattr(host, "RESOURCE", resource)
    monkeypatch.setattr(host, "check_admission", lambda _: 3)
    receipt = {
        k: "proof"
        for k in (
            "mi_head",
            "backup_sha256",
            "restore_point",
            "restore_lsn",
            "base_manifest_sha256",
        )
    }
    calls = []

    def proof():
        calls.append(True)
        for path in paths:
            with pytest.raises(BlockingIOError), host.existing_lease(path):
                pytest.fail("admission fence missing during prewrite")
        return receipt

    with host.admit_analysis_compute():
        with pytest.raises(BlockingIOError), host.existing_lease(paths[0]):
            pytest.fail("another GPU batch admitted")
        for path in paths[1:]:
            with host.existing_lease(path):
                assert path.exists()
        assert not calls
        with host.existing_lease(paths[2]):
            with (
                pytest.raises(BlockingIOError),
                host.admit_analysis_commit(prewrite=proof, wait_seconds=0),
            ):
                pytest.fail("competing writer admitted")
            with host.existing_lease(paths[1]):
                assert not calls
        with host.admit_analysis_commit(prewrite=proof, wait_seconds=0) as (
            limit,
            actual,
        ):
            assert (limit, actual) == (3, receipt)
            for path in paths[:3]:
                with pytest.raises(BlockingIOError), host.existing_lease(path):
                    pytest.fail("commit fence missing")
        assert len(calls) == 1
        for path in paths[1:]:
            with host.existing_lease(path):
                pass
    for path in paths:
        with host.existing_lease(path):
            pass


def test_prewrite_error_never_retried(tmp_path, monkeypatch):
    from scripts.ops import daily_index_recovery_host as host

    for name in (
        "fresh-procurement-priority.lock",
        "mutation.lock",
        "research-backup-gate.lock",
    ):
        (tmp_path / name).touch(mode=0o600)
    monkeypatch.setattr(host, "check_admission", lambda _: 3)
    calls = []

    def fail():
        calls.append(True)
        raise BlockingIOError("prewrite operation failed")

    with (
        pytest.raises(BlockingIOError),
        host._admit_write(tmp_path, prewrite=fail, wait_seconds=120),
    ):
        pytest.fail("unexpected admission")
    assert calls == [True]


def test_compute_wait_does_not_block_historical_commit(tmp_path, monkeypatch):
    from scripts.ops import daily_index_recovery_host as host

    slot = tmp_path / "heavy-slot.lock"
    priority = tmp_path / "fresh-procurement-priority.lock"
    mutation = tmp_path / "mutation.lock"
    for path in (slot, priority, mutation):
        path.touch(mode=0o600)
    monkeypatch.setattr(host, "RUNTIME", tmp_path)
    monkeypatch.setattr(host, "RESOURCE", tmp_path)
    monkeypatch.setattr(host, "check_admission", lambda _: 3)
    active = host.existing_lease(slot)
    active.__enter__()
    calls = []

    def finish_historical_batch(delay):
        assert 0 < delay <= 0.25
        with host.existing_lease(priority), host.existing_lease(mutation):
            calls.append("historical commit not blocked")
        active.__exit__(None, None, None)

    monkeypatch.setattr(host.time, "sleep", finish_historical_batch)
    with host.admit_analysis_compute(wait_seconds=5):
        assert calls == ["historical commit not blocked"]
        with pytest.raises(BlockingIOError), host.existing_lease(slot):
            pytest.fail("second heavy task admitted")
    with (
        host.existing_lease(slot),
        pytest.raises(BlockingIOError),
        host.admit_analysis_compute(wait_seconds=0),
    ):
        pytest.fail("busy heavy slot should refuse without waiting")
