"""Fail-closed checks for the Mac mini SSD backend identity verifier."""
import json
import plistlib

from scripts.runtime import verify_macmini_backend as verify


class _HealthyResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class _Opener:
    def open(self, *_args, **_kwargs):
        return _HealthyResponse()


def _setup(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (tmp_path / "backend.env").write_text("SAFE_TEST=1\n")
    (tmp_path / "backend.env").chmod(0o600)
    (tmp_path / "backend.plist").write_bytes(
        plistlib.dumps({"ProgramArguments": ["/opt/homebrew/bin/node", verify.LAUNCHER]})
    )
    marker = tmp_path / "active.json"
    marker.write_text(
        json.dumps({"commit": "abcd1234", "backend_pid": 42, "source": str(root)})
    )
    monkeypatch.setattr(verify, "ROOT", root)
    monkeypatch.setattr(verify, "CONFIG", tmp_path / "backend.env")
    monkeypatch.setattr(verify, "PLIST", tmp_path / "backend.plist")
    monkeypatch.setattr(verify, "RUNTIME", marker)
    monkeypatch.setattr(verify.urllib.request, "build_opener", lambda *_: _Opener())

    def fake_run(*args):
        if args[0] == "git":
            if "branch" in args:
                return 0, "main"
            if "rev-parse" in args:
                return 0, "abcd1234"
            if "status" in args:
                return 0, ""
        if args[0] == "gh":
            return 0, "abcd1234"
        if args[0] == "launchctl":
            return 0, "state = running"
        if args[0] == "lsof" and "-iTCP:8001" in args:
            return 0, "42"
        if args[0] == "lsof":
            return 0, "p42\nfcwd\nn" + str(root)
        return 1, ""

    monkeypatch.setattr(verify, "run", fake_run)
    return marker


def test_complete_source_identity_is_healthy(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    result = verify.check()
    assert result["status"] == "OK"
    assert all(result["checks"].values())


def test_live_process_commit_mismatch_fails_closed(tmp_path, monkeypatch):
    marker = _setup(tmp_path, monkeypatch)
    marker.write_text(json.dumps({"commit": "old1234", "backend_pid": 42}))
    result = verify.check()
    assert result["status"] == "DRIFT_OR_DEGRADED"
    assert result["checks"]["active_backend_commit_matches_main"] is False


def test_git_status_failure_not_treated_as_clean(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    previous = verify.run

    def fake_run(*args):
        if args[0] == "git" and "status" in args:
            return 1, ""
        return previous(*args)

    monkeypatch.setattr(verify, "run", fake_run)
    result = verify.check()
    assert result["status"] == "DRIFT_OR_DEGRADED"
    assert result["checks"]["local_main_clean"] is False
