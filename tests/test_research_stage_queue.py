import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime

import pytest

from scripts.research.stage_queue import JobSpec, Lane, QueueStore, Stage
from scripts.research.typed_receipts import StageReceipt

A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64


def discovery():
    return JobSpec("etp_gpb", "etp", Stage.DISCOVER, None, A, B)


def detail(input_sha=C):
    return JobSpec("etp_gpb", "etp", Stage.DETAIL, "123", A, input_sha)


def discover_bytes(*members, empty=False):
    return json.dumps({"members": list(members), "explicit_empty": empty}, sort_keys=True).encode()


def make_receipt(q, job_id, artifact, members=("123",), *, explicit_empty=False):
    row = q.get(job_id)
    spec = json.loads(row["spec"])
    return StageReceipt(
        job_id=job_id, source=row["source"], namespace=row["namespace"],
        stage=row["stage"], external_id=row["external_id"],
        unit_sha256=spec["unit_sha256"], input_sha256=row["input_sha256"],
        parent_receipt_sha256=row["input_sha256"] if row["parent_id"] else None,
        artifact_sha256=hashlib.sha256(artifact).hexdigest(), artifact_size=len(artifact),
        members=tuple(members), explicit_empty=explicit_empty,
    )


def test_dedup_and_lane_promotion(tmp_path):
    db = QueueStore(tmp_path / "queue.db")
    d = discovery()
    assert db.enqueue(d, Lane.HISTORY) == db.enqueue(d, Lane.FRESH)
    db.enqueue(d, Lane.HISTORY)
    assert db.claim(Lane.HISTORY, Stage.DISCOVER, "etp_gpb") is None
    job = db.claim(Lane.FRESH, Stage.DISCOVER, "etp_gpb")
    assert job["job_id"] == d.job_id
    assert db.claim(Lane.FRESH, Stage.DISCOVER, "etp_gpb") is None


def test_interruption_keeps_inflight_and_receipt_is_idempotent(tmp_path):
    path = tmp_path / "queue.db"
    q = QueueStore(path)
    job_id = q.enqueue(discovery(), Lane.HISTORY)
    job = q.claim(Lane.HISTORY, Stage.DISCOVER, "etp_gpb")
    q = QueueStore(path)
    assert q.get(job_id)["status"] == "running"
    assert q.claim(Lane.HISTORY, Stage.DISCOVER, "etp_gpb") is None
    raw = discover_bytes("123")
    receipt = make_receipt(q, job_id, raw)
    with pytest.raises(ValueError, match="attempt"):
        q.complete(job_id, "foreign", receipt, raw)
    digest = q.complete(job_id, job["attempt"], receipt, raw)
    assert q.complete(job_id, job["attempt"], receipt, raw) == digest
    assert q.get(job_id)["receipt_sha256"] == receipt.sha256
    with pytest.raises(ValueError, match="artifact"):
        q.complete(job_id, job["attempt"], receipt, b"tamper")
    with pytest.raises(ValueError, match="different completed"):
        extra = json.dumps({"members": ["123"], "explicit_empty": False, "extra": 1}).encode()
        changed = replace(receipt, artifact_sha256=hashlib.sha256(extra).hexdigest(), artifact_size=len(extra))
        q.complete(job_id, job["attempt"], changed, extra)


def test_parent_receipt_binding_and_stage_independence(tmp_path):
    q = QueueStore(tmp_path / "queue.db")
    p = q.enqueue(discovery(), Lane.FRESH)
    with pytest.raises(ValueError, match="receipt"):
        q.enqueue(detail(), Lane.FRESH, parent_id=p)
    job = q.claim(Lane.FRESH, Stage.DISCOVER, "etp_gpb")
    raw = discover_bytes("123")
    digest = q.complete(p, job["attempt"], make_receipt(q, p, raw), raw)
    with pytest.raises(ValueError, match="receipt"):
        q.enqueue(detail(D), Lane.HISTORY, parent_id=p)
    with pytest.raises(ValueError, match="receipt"):
        q.enqueue(replace(detail(digest), namespace="gos"), Lane.HISTORY, parent_id=p)
    with pytest.raises(ValueError, match="receipt"):
        q.enqueue(replace(detail(digest), external_id="456"), Lane.FRESH, parent_id=p)
    child = q.enqueue(detail(digest), Lane.FRESH, parent_id=p)
    assert q.claim(Lane.FRESH, Stage.INDEX, "etp_gpb") is None
    d = q.claim(Lane.FRESH, Stage.DETAIL, "etp_gpb")
    assert d["job_id"] == child
    detail_raw = b"exact detail artifact"
    q.complete(child, d["attempt"], make_receipt(q, child, detail_raw), detail_raw)
    wrong = JobSpec("etp_gpb", "etp", Stage.ATTACHMENT, "456", A, q.get(child)["receipt_sha256"])
    with pytest.raises(ValueError, match="receipt"):
        q.enqueue(wrong, Lane.FRESH, parent_id=child)


def test_concurrent_claim_only_once(tmp_path):
    path = tmp_path / "queue.db"
    q = QueueStore(path)
    q.enqueue(discovery(), Lane.FRESH)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: QueueStore(path).claim(Lane.FRESH, Stage.DISCOVER, "etp_gpb"),
                range(8),
            )
        )
    assert sum(x is not None for x in results) == 1


def test_review_requires_explicit_reconciliation(tmp_path):
    q = QueueStore(tmp_path / "queue.db")
    j = q.enqueue(discovery(), Lane.HISTORY)
    c = q.claim(Lane.HISTORY, Stage.DISCOVER, "etp_gpb")
    q.review(j, c["attempt"], "ambiguous_write")
    assert q.get(j)["status"] == "review"
    q.enqueue(discovery(), Lane.FRESH)
    assert q.claim(Lane.FRESH, Stage.DISCOVER, "etp_gpb") is None
    with pytest.raises(ValueError):
        replace(detail(), namespace="sale")
    with pytest.raises(ValueError):
        replace(discovery(), input_sha256="bad")


def test_receipt_scope_and_artifact_tampering_fail_closed(tmp_path):
    q = QueueStore(tmp_path / "queue.db")
    job_id = q.enqueue(discovery(), Lane.FRESH)
    attempt = q.claim(Lane.FRESH, Stage.DISCOVER, "etp_gpb")["attempt"]
    artifact = discover_bytes("123")
    receipt = make_receipt(q, job_id, artifact)
    for change in ({"source": "sibur"}, {"namespace": "gos"},
                   {"unit_sha256": B}, {"input_sha256": C}, {"stage": "detail"}):
        try:
            altered = replace(receipt, **change)
        except (TypeError, ValueError):
            continue  # Malformed typed envelope is already refused.
        with pytest.raises((TypeError, ValueError)):
            q.complete(job_id, attempt, altered, artifact)
        assert q.get(job_id)["status"] == "running"
    with pytest.raises(ValueError, match="membership"):
        mismatch = make_receipt(q, job_id, artifact, members=("456",))
        q.complete(job_id, attempt, mismatch, artifact)
    with pytest.raises(ValueError, match="artifact"):
        q.complete(job_id, attempt, receipt, artifact + b" ")
    assert q.complete(job_id, attempt, receipt, artifact) == receipt.sha256


def test_discovery_empty_requires_explicit_evidence_and_blocks_child(tmp_path):
    q = QueueStore(tmp_path / "queue.db")
    parent = q.enqueue(discovery(), Lane.FRESH)
    token = q.claim(Lane.FRESH, Stage.DISCOVER, "etp_gpb")["attempt"]
    empty = discover_bytes(empty=True)
    with pytest.raises(ValueError, match="empty"):
        make_receipt(q, parent, empty, members=())
    receipt = make_receipt(q, parent, empty, members=(), explicit_empty=True)
    assert q.complete(parent, token, receipt, empty) == receipt.sha256
    with pytest.raises(ValueError, match="receipt"):
        q.enqueue(detail(receipt.sha256), Lane.FRESH, parent_id=parent)


def test_interruption_quarantine_keeps_original_attempt_and_blocks_replay(tmp_path):
    path = tmp_path / "queue.db"
    q = QueueStore(path)
    id_ = q.enqueue(discovery(), Lane.HISTORY)
    assert datetime.fromisoformat(q.get(id_)["created_at"]).tzinfo
    attempt = q.claim(Lane.HISTORY, Stage.DISCOVER, "etp_gpb")["attempt"]
    q = QueueStore(path)  # Restart retains the in-flight attempt.
    assert datetime.fromisoformat(q.get(id_)["started_at"]).tzinfo
    with pytest.raises(ValueError, match="attempt"):
        q.reconcile_interrupted(id_, "not-the-attempt")
    q.reconcile_interrupted(id_, attempt)
    q.reconcile_interrupted(id_, attempt)  # crash retry of reconciliation is a no-op
    row = q.get(id_)
    assert row["status"] == "review" and row["review_code"] == "interrupted_unverified"
    assert datetime.fromisoformat(row["finished_at"]).tzinfo
    assert q.claim(Lane.HISTORY, Stage.DISCOVER, "etp_gpb") is None
    assert q.enqueue(discovery(), Lane.FRESH) == id_
    with pytest.raises(ValueError, match="not running"):
        q.complete(id_, attempt, make_receipt(q, id_, discover_bytes("123")), discover_bytes("123"))
    assert q.get(id_)["status"] == "review"


def test_bounded_pending_query_cannot_claim_or_auto_schedule(tmp_path):
    q = QueueStore(tmp_path / "queue.db")
    for i in range(35):
        q.enqueue(replace(discovery(), unit_sha256=f"{i:064x}"), Lane.HISTORY)
    assert len(q.pending(Lane.HISTORY, Stage.DISCOVER, "etp_gpb", limit=32)) == 32
    assert len(q.pending(Lane.HISTORY, Stage.DISCOVER, "etp_gpb", limit=3)) == 3
    assert q.pending(Lane.FRESH, Stage.DISCOVER, "etp_gpb") == ()
    for limit in (0, 33, True, -1, 1.5):
        with pytest.raises(ValueError, match="pending"):
            q.pending(Lane.HISTORY, Stage.DISCOVER, "etp_gpb", limit=limit)
    assert q.get(q.pending(Lane.HISTORY, Stage.DISCOVER, "etp_gpb")[0])["status"] == "queued"


def test_legacy_hash_only_done_row_never_authorizes_new_members(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    spec = discovery()
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY,spec TEXT NOT NULL,source TEXT NOT NULL,
            namespace TEXT NOT NULL,external_id TEXT,stage TEXT NOT NULL,
            lane TEXT NOT NULL CHECK(lane IN ('fresh','history')),
            status TEXT NOT NULL CHECK(status IN ('queued','running','done','review')),
            input_sha256 TEXT NOT NULL,parent_id TEXT REFERENCES jobs(job_id),
            attempt TEXT,receipt_sha256 TEXT,review_code TEXT)""")
        db.execute("""INSERT INTO jobs (job_id,spec,source,namespace,external_id,
            stage,lane,status,input_sha256,attempt,receipt_sha256)
            VALUES (?,?,?,?,? ,?,'history','done',?,?,?)""",
            (spec.job_id, spec.canonical, spec.source, spec.namespace, None,
             str(spec.stage), spec.input_sha256, "old", C))
    q = QueueStore(path)  # In-place additive SQLite migration.
    legacy = q.get(spec.job_id)
    assert legacy["status"] == "done" and legacy["receipt_json"] is None
    with pytest.raises(ValueError, match="receipt"):
        q.enqueue(detail(C), Lane.FRESH, parent_id=spec.job_id)
    assert q.get(spec.job_id)["status"] == "done"


def test_discovery_duplicate_json_membership_key_is_not_accepted(tmp_path):
    q = QueueStore(tmp_path / "queue.db")
    id_ = q.enqueue(discovery(), Lane.FRESH)
    attempt = q.claim(Lane.FRESH, Stage.DISCOVER, "etp_gpb")["attempt"]
    duplicate = b'{"members":["456"],"members":["123"],"explicit_empty":false}'
    receipt = make_receipt(q, id_, duplicate)
    with pytest.raises(ValueError, match="discovery membership artifact invalid"):
        q.complete(id_, attempt, receipt, duplicate)
    assert q.get(id_)["status"] == "running"
    with pytest.raises(ValueError, match="duplicate receipt"):
        make_receipt(q, id_, discover_bytes("123","123"), members=("123","123"))


def test_concurrent_identical_completion_is_idempotent(tmp_path):
    path = tmp_path / "queue.db"
    q = QueueStore(path)
    id_ = q.enqueue(discovery(), Lane.FRESH)
    token = q.claim(Lane.FRESH, Stage.DISCOVER, "etp_gpb")["attempt"]
    artifact = discover_bytes("123", "456")
    receipt = make_receipt(q, id_, artifact, members=("123", "456"))
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(
            lambda _: QueueStore(path).complete(id_, token, receipt, artifact), range(6)))
    assert set(results) == {receipt.sha256}
    assert q.get(id_)["status"] == "done"
    assert datetime.fromisoformat(q.get(id_)["finished_at"]).tzinfo
