"""Automatic per-file deferral preserves safety gates and provenance."""
import hashlib
import json
from unittest.mock import Mock

import pytest

from scripts.research.autonomous_runner import (
    Blocked, FileReview, Runner, classify_file_review, FILE_REVIEW_CIRCUIT_LIMIT,
)


@pytest.mark.parametrize("output,code,step,valid", [
    (b"296c61a77ef6 extracted 6\n45c41d592a91 review CalledProcessError\n", 2, "member_index_batch_index", True),
    (b"45c41d592a91 review BadZipFile\n", 2, "archive_index_batch", True),
    (b"45c41d592a91 review ValueError\n", 2, "member_index_batch_index", False),
    (b"45c41d592a91 review TimeoutExpired\n", 2, "member_index_batch_index", False),
    (b"45c41d592a91 review CalledProcessError\n", 1, "member_index_batch_index", False),
    (b"45c41d592a91 review CalledProcessError\n", 2, "member registry", False),
    (b"45c41d592a91 review CalledProcessError\n45c41d592a91 review CalledProcessError\n", 2, "member_index_batch_index", False),
    (b"garbage review CalledProcessError\n", 2, "member_index_batch_index", False),
])
def test_classify_only_explicit_file_failures(output,code,step,valid):
    assert (classify_file_review(step, ["--mode", "index"], code, output) is not None) is valid


def fixture(tmp_path, kind="member"):
    run = Runner.__new__(Runner)
    run.root = run.sibur = tmp_path
    run.docs = tmp_path / "documents"; run.docs.mkdir()
    base = tmp_path / "sibur-archive-expansion-v86"; base.mkdir()
    src = base / "nested-members" if kind == "member" else tmp_path / "sibur-archive-discovery/categories/documents"
    src.mkdir(parents=True)
    raw = b"verified original"
    h = hashlib.sha256(raw).hexdigest()
    name = h + ".pdf"
    for p in (src/name, run.docs/name):
        p.write_bytes(raw)
    index = {"good": {}}
    lane = {"archive_synced_count": 1, "index_inflight": True}
    run.state = {"lanes": {"sibur": lane}}
    run.update = lambda _, **kw: lane.update(kw)
    run.reconcile_index = Mock()
    run.cmd = Mock(side_effect=[b'{"status":"ok"}', b'{"status":"ok"}', b'[]'])
    row = {"sha256": h, "file": name}
    row.update({"folder": "nested-members", "bytes": len(raw)} if kind == "member" else {"size_bytes": len(raw)})
    plan = tmp_path/"plan.json"
    plan.write_text(json.dumps({"schema": "sibur_member_index_plan_v1" if kind == "member" else "sibur_archive_index_bridge_v1", "ready": [row]}))
    digest = hashlib.sha256(plan.read_bytes()).hexdigest()
    err = FileReview("member_index_batch_index" if kind=="member" else "archive_index_batch", "index", [(h[:12], "CalledProcessError")])
    ledger = base / "member-index-queue-reviews-v1.json"
    return run, lane, index, h, plan, digest, err, ledger, src/name


@pytest.mark.parametrize("kind", ["member", "archive"])
def test_defer_preserves_original_and_marks_review(tmp_path,kind):
    r,lane,index,h,p,d,e,ledger,source = fixture(tmp_path,kind)
    assert r.defer_file_reviews(e,p,d,kind,index,0) == [h]
    item = json.loads(ledger.read_text())["rows"][h]
    assert item["reason"] == "auto_deferred_file_processing_failure"
    assert item["source_preserved"] and item["review_required"]
    assert item["plan_sha256"] == d and item["attempts"] == 1
    assert item["scope"] == kind and item["phase"] == "index"
    assert source.read_bytes() == b"verified original"
    assert lane["index_inflight"] is False
    assert lane["file_review_failure_streak"] == 1
    r.reconcile_index.assert_called_once_with(index)


@pytest.mark.parametrize("fault,match", [
    ("already_indexed", "already indexed"),
    ("tampered", "hash mismatch"),
    ("health", "unhealthy"),
    ("partial_commit", "exists in DP"),
    ("ambiguous", "ambiguous"),
    ("sync", "synchronized"),
    ("reconcile", "aggregate mismatch"),
])
def test_integrity_and_service_failure_do_not_defer(tmp_path,fault,match):
    r,lane,index,h,p,d,e,ledger,source = fixture(tmp_path)
    if fault == "already_indexed":
        index[h] = {}; lane["archive_synced_count"] += 1
    if fault == "tampered":
        source.write_bytes(b"changed  original")
    if fault == "health":
        r.cmd.side_effect = [b'{"status":"error"}']
    if fault == "partial_commit":
        r.cmd.side_effect = [b'{"status":"ok"}', b'{"status":"ok"}', json.dumps(["content-sha256://"+h]).encode()]
    if fault == "ambiguous":
        e = FileReview(e.step,e.mode,[("a"*12,"CalledProcessError")])
    if fault == "sync":
        lane["archive_synced_count"] = 3
    if fault == "reconcile":
        r.reconcile_index.side_effect = Blocked("aggregate mismatch")
    with pytest.raises(Blocked,match=match):
        r.defer_file_reviews(e,p,d,"member",index,0)
    assert not ledger.exists() and lane["index_inflight"] is True


def test_circuit_breaker_keeps_review_but_stops_systemic_failure(tmp_path):
    r,lane,index,h,p,d,e,ledger,_ = fixture(tmp_path)
    lane["file_review_failure_streak"] = FILE_REVIEW_CIRCUIT_LIMIT-1
    with pytest.raises(Blocked,match="circuit breaker"):
        r.defer_file_reviews(e,p,d,"member",index,0)
    assert h in json.loads(ledger.read_text())["rows"]
    assert lane["index_inflight"] is False


def test_success_resets_failure_streak(tmp_path):
    r,lane,index,h,p,d,e,ledger,_ = fixture(tmp_path)
    lane["file_review_failure_streak"] = FILE_REVIEW_CIRCUIT_LIMIT-1
    assert r.defer_file_reviews(e,p,d,"member",index,1) == [h]
    assert lane["file_review_failure_streak"] == 0


def test_duplicate_ledger_hash_fails_closed(tmp_path):
    r,lane,index,h,p,d,e,ledger,_ = fixture(tmp_path)
    ledger.write_text(json.dumps({"schema":"sibur_member_queue_structural_reviews_v1","rows":{h:{"sha256":h,"reason":"previous"}}}))
    old = ledger.read_bytes()
    with pytest.raises(Blocked,match="returned"):
        r.defer_file_reviews(e,p,d,"member",index,0)
    assert ledger.read_bytes() == old and lane["index_inflight"] is True
