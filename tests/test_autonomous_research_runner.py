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
