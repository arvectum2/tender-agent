import json

import pytest

from scripts.research.autonomous_runner import Blocked, Runner, atomic, planned


def test_counter_and_atomic_state(tmp_path):
    path = tmp_path / "state.json"
    atomic(path, {"value": 1})
    atomic(path, {"value": 2})
    assert json.loads(path.read_text()) == {"value": 2}
    assert not list(tmp_path.glob("*.partial"))
    assert planned("x\nattempted 30 total captured 220\n", "attempted") == 30
    assert planned("planned 0\n", "planned") == 0
    with pytest.raises(ValueError):
        planned("unexpected log", "planned")


def test_failure_isolated_and_blocked_not_retried(tmp_path):
    r = Runner(tmp_path, tmp_path, tmp_path, tmp_path)
    def fail():
        raise Blocked("review required")
    r.guarded("gpb", fail)
    assert r.state["lanes"]["gpb"]["status"] == "blocked"
    r.guarded("gpb", lambda: pytest.fail("blind retry"))
    r.guarded("sibur", lambda: r.update("sibur", status="exhausted"))
    assert r.state["lanes"]["sibur"]["status"] == "exhausted"
    assert json.loads(r.state_path.read_text())["lanes"]["gpb"]["error"] == "review required"


def test_interrupted_index_is_not_replayed(tmp_path):
    r = Runner(tmp_path, tmp_path, tmp_path, tmp_path)
    r.update("sibur", index_inflight=True)
    r.guarded("sibur", r.sibur_lane)
    assert r.state["lanes"]["sibur"]["status"] == "blocked"
    assert "interrupted" in r.state["lanes"]["sibur"]["error"]


def test_gpb_multiple_batches_are_one_run(tmp_path, monkeypatch):
    r = Runner(tmp_path, tmp_path, tmp_path, tmp_path)
    for folder in ("historical-priority-details", "active-priority-details"):
        p = r.gpb_root / folder
        p.mkdir(parents=True)
        for name in ("receipts.json", "document-pilot-receipts.json"):
            atomic(p / name, [])
    detail_calls = []
    def module(lane, repo, name, *args, **kwargs):
        if name == "capture_gpb_priority_details":
            detail_calls.append(name)
            return b"attempted 30\n" if len(detail_calls) < 3 else b"attempted 0\n"
        return b"attempted 0\n"
    monkeypatch.setattr(r, "module", module)
    monkeypatch.setattr(r, "gpb_sync", lambda stage: None)
    monkeypatch.setattr("scripts.research.autonomous_runner.time.sleep", lambda _: None)
    # Sandbox CI filesystems may be smaller than production.
    from collections import namedtuple
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr("scripts.research.autonomous_runner.shutil.disk_usage", lambda _: Usage(100*1024**3, 0, 100*1024**3))
    r.guarded("gpb", r.gpb_lane)
    assert len(detail_calls) == 3
    assert r.state["lanes"]["gpb"]["cycles"] == 3
    assert r.state["lanes"]["gpb"]["status"] == "exhausted"


def test_archive_refresh_append_preserves_and_checks_identity(tmp_path, monkeypatch):
    import hashlib
    r = Runner(tmp_path, tmp_path, tmp_path, tmp_path)
    folder = tmp_path / "sibur-sales-map-20261115"
    folder.mkdir()
    bridge = folder / "archive-index-bridge-v1.json"
    old = {"schema": "sibur_archive_index_bridge_v1", "ready": [{"sha256": "a"*64}], "review": []}
    atomic(bridge, old)
    digest = hashlib.sha256(bridge.read_bytes()).hexdigest()
    r.update("sibur", status="running", archive_bridge_sha256=digest)
    prepared = folder / "archive-index-bridge-auto-20261116T081835120216Z.json"
    new = {**old, "ready": old["ready"] + [{"sha256": "b"*64}]}
    atomic(prepared, new)
    new_digest = hashlib.sha256(prepared.read_bytes()).hexdigest()
    monkeypatch.setattr(r, "local_index", lambda: {"a"*64: {}})
    result = {"prior_digest": digest, "indexed_count": 1, "new_ready": 1,
              "file": prepared.name, "digest": new_digest}
    monkeypatch.setattr(r, "module", lambda *a, **k: json.dumps(result).encode())
    assert r.refresh_archive_bridge("sibur", bridge, digest) == (new_digest, new["ready"])
    assert json.loads(bridge.read_text()) == new
    assert r.state["lanes"]["sibur"]["archive_bridge_sha256"] == new_digest
    assert len(list(folder.glob("archive-index-bridge-before-auto-*.json"))) == 1
    with pytest.raises(Blocked, match="changed"):
        r.refresh_archive_bridge("sibur", bridge, digest)


def test_archive_refresh_empty_does_not_change_bridge(tmp_path, monkeypatch):
    import hashlib
    r = Runner(tmp_path, tmp_path, tmp_path, tmp_path)
    bridge = tmp_path / "bridge.json"
    atomic(bridge, {"ready": []})
    digest = hashlib.sha256(bridge.read_bytes()).hexdigest()
    monkeypatch.setattr(r, "local_index", lambda: {})
    monkeypatch.setattr(r, "module", lambda *a, **k: json.dumps({"prior_digest": digest, "indexed_count": 0, "new_ready": 0}).encode())
    assert r.refresh_archive_bridge("sibur", bridge, digest) is None
    assert hashlib.sha256(bridge.read_bytes()).hexdigest() == digest


def test_drained_archive_refresh_continues_without_restart(tmp_path, monkeypatch):
    import hashlib
    r = Runner(tmp_path, tmp_path, tmp_path, tmp_path)
    folder = tmp_path / "sibur-sales-map-20261115"
    folder.mkdir()
    bridge = folder / "archive-index-bridge-v1.json"
    atomic(bridge, {"ready": []})
    digest = hashlib.sha256(bridge.read_bytes()).hexdigest()
    r.update("sibur", archive_bridge_sha256=digest, archive_synced_count=0)
    monkeypatch.setattr(r, "local_index", lambda: {})
    monkeypatch.setattr(r, "reconcile_index", lambda _: None)
    monkeypatch.setattr(r, "gate", lambda _: tmp_path / "gate.json")
    monkeypatch.setattr("scripts.research.autonomous_runner.time.sleep", lambda _: None)
    calls = []
    def module(lane, repo, name, *args, **kwargs):
        calls.append(args[args.index("--digest")+1])
        assert args[args.index("--limit")+1] == 10
        assert kwargs["timeout"] == 2050
        return b"planned 0\n"
    monkeypatch.setattr(r, "module", module)
    refreshes = []
    def refresh(lane, path, sha):
        refreshes.append(sha)
        return ("b"*64, []) if len(refreshes)==1 else None
    monkeypatch.setattr(r, "refresh_archive_bridge", refresh)
    r.archive_index_lane()
    assert calls == [digest, digest, "b"*64, "b"*64]
    assert refreshes == [digest, "b"*64]
    assert r.state["lanes"]["sibur"]["status"] == "exhausted"
    assert r.state["lanes"]["sibur"]["index_inflight"] is False


def test_review_only_refresh_commits_bounded_structural_progress(tmp_path, monkeypatch):
    import hashlib,json
    from scripts.research.autonomous_runner import Runner
    import inspect
    # Construct the minimal runner state in the same way as the append test.
    r=Runner(tmp_path,tmp_path,tmp_path,tmp_path)
    r.run.mkdir(parents=True,exist_ok=True)
    bridge=tmp_path/"archive-index-bridge-v1.json"
    old={"schema":"sibur_archive_index_bridge_v1","ready":[],"review":[]}
    bridge.write_text(json.dumps(old));digest=hashlib.sha256(bridge.read_bytes()).hexdigest()
    new={**old,"review":[{"sha256":"a"*64,"reason":"structure_review"}]}
    p=tmp_path/"archive-index-bridge-auto-20261116T160000000001Z.json";p.write_text(json.dumps(new))
    new_digest=hashlib.sha256(p.read_bytes()).hexdigest()
    r.state_path.write_text(json.dumps(r.state))
    monkeypatch.setattr(r,"local_index",lambda:{})
    monkeypatch.setattr(r,"module",lambda *a,**k:json.dumps({"new_ready":0,"new_review":1,"prior_digest":digest,"indexed_count":0,"file":p.name,"digest":new_digest}))
    assert r.refresh_archive_bridge("sibur",bridge,digest)==(new_digest,[])
    assert json.loads(bridge.read_text())==new
