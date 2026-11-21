"""Isolated durable job ledger. No source calls, production writes or worker."""

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from scripts.research.source_catalog import SOURCES, SourceIdentity
from scripts.research.typed_receipts import StageReceipt


class Stage(StrEnum):
    DISCOVER = "discover"
    DETAIL = "detail"
    ATTACHMENT = "attachment"
    EXTRACT = "extract"
    INDEX = "index"
    OUTCOME = "outcome"


class Lane(StrEnum):
    FRESH = "fresh"
    HISTORY = "history"


PARENTS = {
    Stage.DETAIL: {Stage.DISCOVER},
    Stage.ATTACHMENT: {Stage.DETAIL},
    Stage.EXTRACT: {Stage.ATTACHMENT},
    Stage.INDEX: {Stage.EXTRACT},
    Stage.OUTCOME: {Stage.DETAIL, Stage.EXTRACT},
}


def check_hash(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("invalid SHA-256")


@dataclass(frozen=True, slots=True)
class JobSpec:
    source: str
    namespace: str
    stage: Stage
    external_id: str | None
    unit_sha256: str
    input_sha256: str

    def __post_init__(self):
        if not isinstance(self.stage, Stage):
            raise TypeError("invalid stage")
        source = SOURCES.get(self.source)
        if source is None or self.namespace not in source.namespaces:
            raise ValueError("unknown source namespace")
        check_hash(self.unit_sha256)
        check_hash(self.input_sha256)
        if self.stage == Stage.DISCOVER:
            if self.external_id is not None:
                raise ValueError("discovery scope is not a procurement identity")
        else:
            SourceIdentity(self.source, self.namespace, self.external_id)
            if self.namespace == "sale":
                raise ValueError("sale is observation-only")

    @property
    def canonical(self):
        return json.dumps(
            asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    @property
    def job_id(self):
        return hashlib.sha256(("source-job-v1:" + self.canonical).encode()).hexdigest()


class QueueStore:
    """SQLite prototype: caller supplies an isolated local ledger file.

    A running job is never automatically reclaimed. Completion requires the
    current attempt token and a receipt hash, not merely a successful response.
    The caller must verify artifact bytes and authorization outside this ledger.
    """

    def __init__(self, path: Path):
        if path.is_symlink():
            raise ValueError("symlink ledger")
        self.path = path
        with self.transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY, spec TEXT NOT NULL,
                source TEXT NOT NULL, namespace TEXT NOT NULL,
                external_id TEXT, stage TEXT NOT NULL,
                lane TEXT NOT NULL CHECK(lane IN ('fresh','history')),
                status TEXT NOT NULL CHECK(status IN ('queued','running','done','review')),
                input_sha256 TEXT NOT NULL, parent_id TEXT REFERENCES jobs(job_id),
                attempt TEXT, receipt_sha256 TEXT, review_code TEXT,
                receipt_json TEXT, created_at TEXT, started_at TEXT, finished_at TEXT
            )""")
            # Old isolated prototype records remain auditable but their
            # hash-only receipts cannot authorize downstream membership.
            columns = {r["name"] for r in db.execute("PRAGMA table_info(jobs)")}
            for column in ("receipt_json", "created_at", "started_at", "finished_at"):
                if column not in columns:
                    db.execute(f"ALTER TABLE jobs ADD COLUMN {column} TEXT")
            db.execute(
                "CREATE INDEX IF NOT EXISTS queue_pending ON jobs(lane,source,stage,status)"
            )

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def enqueue(self, spec: JobSpec, lane: Lane, *, parent_id=None):
        if not isinstance(lane, Lane):
            raise TypeError("unknown lane")
        with self.transaction() as db:
            if spec.stage == Stage.DISCOVER:
                if parent_id is not None:
                    raise ValueError("discovery cannot have a parent")
            else:
                p = db.execute(
                    "SELECT * FROM jobs WHERE job_id=?", (parent_id,)
                ).fetchone()
                if (
                    p is None
                    or p["status"] != "done"
                    or p["stage"] not in PARENTS[spec.stage]
                    or p["source"] != spec.source
                    or p["namespace"] != spec.namespace
                    or p["receipt_sha256"] != spec.input_sha256
                    or p["receipt_json"] is None
                    or (
                        p["stage"] == Stage.DISCOVER
                        and spec.external_id not in json.loads(p["receipt_json"])["members"]
                    )
                    or (
                        p["stage"] != Stage.DISCOVER
                        and p["external_id"] != spec.external_id
                    )
                ):
                    raise ValueError("missing or mismatched completed input receipt")
            old = db.execute(
                "SELECT * FROM jobs WHERE job_id=?", (spec.job_id,)
            ).fetchone()
            if old:
                if old["spec"] != spec.canonical:
                    raise ValueError("job hash collision")
                if old["status"] == "queued" and lane == Lane.FRESH:
                    db.execute(
                        "UPDATE jobs SET lane='fresh' WHERE job_id=?", (spec.job_id,)
                    )
                return spec.job_id
            db.execute(
                """INSERT INTO jobs(job_id,spec,source,namespace,external_id,stage,lane,status,input_sha256,parent_id,created_at)
                   VALUES(?,?,?,?,?,?,?,'queued',?,?,?)""",
                (
                    spec.job_id,
                    spec.canonical,
                    spec.source,
                    spec.namespace,
                    spec.external_id,
                    str(spec.stage),
                    str(lane),
                    spec.input_sha256,
                    parent_id,
                    datetime.now(UTC).isoformat(),
                ),
            )
            return spec.job_id

    def claim(self, lane: Lane, stage: Stage, source: str):
        if (
            not isinstance(lane, Lane)
            or not isinstance(stage, Stage)
            or source not in SOURCES
        ):
            raise ValueError("unknown queue")
        with self.transaction() as db:
            row = db.execute(
                """SELECT * FROM jobs WHERE lane=? AND stage=? AND source=? AND status='queued'
                   ORDER BY rowid LIMIT 1""",
                (str(lane), str(stage), source),
            ).fetchone()
            if row is None:
                return None
            attempt = uuid4().hex
            db.execute(
                "UPDATE jobs SET status='running', attempt=?, started_at=? WHERE job_id=?",
                (attempt, datetime.now(UTC).isoformat(), row["job_id"]),
            )
            return {**dict(row), "status": "running", "attempt": attempt}

    def get(self, job_id):
        with self.transaction() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            return dict(row) if row is not None else None

    def pending(self, lane: Lane, stage: Stage, source: str, *, limit: int = 20):
        """Bounded observation only, not a worker or automatic retry."""
        if (not isinstance(lane, Lane) or not isinstance(stage, Stage)
                or source not in SOURCES or type(limit) is not int or not 1 <= limit <= 32):
            raise ValueError("invalid pending query")
        with self.transaction() as db:
            rows = db.execute(
                "SELECT job_id FROM jobs WHERE lane=? AND stage=? AND source=? "
                "AND status='queued' ORDER BY rowid LIMIT ?",
                (lane, stage, source, limit),
            ).fetchall()
            return tuple(row["job_id"] for row in rows)

    def complete(self, job_id, attempt, receipt: StageReceipt, artifact_bytes: bytes):
        """Fail closed on exact typed membership, immutable scope and output bytes."""
        if not isinstance(receipt, StageReceipt):
            raise TypeError("typed receipt required")
        receipt.verify_artifact(artifact_bytes)
        with self.transaction() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None or row["attempt"] != attempt or receipt.job_id != job_id:
                raise ValueError("attempt identity mismatch")
            spec = json.loads(row["spec"])
            if (receipt.source != row["source"] or receipt.namespace != row["namespace"]
                    or receipt.stage != row["stage"]
                    or receipt.external_id != row["external_id"]
                    or receipt.unit_sha256 != spec["unit_sha256"]
                    or receipt.input_sha256 != row["input_sha256"]):
                raise ValueError("receipt immutable scope mismatch")
            parent = (db.execute("SELECT * FROM jobs WHERE job_id=?", (row["parent_id"],)).fetchone()
                      if row["parent_id"] is not None else None)
            if ((parent is None and receipt.parent_receipt_sha256 is not None)
                    or (parent is not None and (
                        parent["status"] != "done"
                        or parent["receipt_json"] is None
                        or parent["receipt_sha256"] != receipt.parent_receipt_sha256
                        or parent["receipt_sha256"] != row["input_sha256"]
                    ))):
                raise ValueError("receipt parent binding mismatch")
            if row["status"] == "done":
                if row["receipt_sha256"] == receipt.sha256 and row["receipt_json"] == receipt.canonical:
                    return receipt.sha256
                raise ValueError("different completed receipt")
            if row["status"] != "running":
                raise ValueError("job not running")
            db.execute(
                "UPDATE jobs SET status='done',receipt_sha256=?,receipt_json=?,finished_at=? WHERE job_id=?",
                (receipt.sha256, receipt.canonical, datetime.now(UTC).isoformat(), job_id),
            )
            return receipt.sha256

    def reconcile_interrupted(self, job_id, attempt):
        """Idempotently quarantine an exact crashed attempt; never replay."""
        with self.transaction() as db:
            row = db.execute("SELECT status,attempt,review_code FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None or row["attempt"] != attempt:
                raise ValueError("attempt identity mismatch")
            if row["status"] == "review" and row["review_code"] == "interrupted_unverified":
                return
            if row["status"] != "running":
                raise ValueError("attempt not running")
            db.execute(
                "UPDATE jobs SET status='review',review_code='interrupted_unverified',finished_at=? WHERE job_id=?",
                (datetime.now(UTC).isoformat(), job_id),
            )

    def review(self, job_id, attempt, code):
        if (
            not isinstance(code, str)
            or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", code) is None
        ):
            raise ValueError("invalid review code")
        with self.transaction() as db:
            cursor = db.execute(
                "UPDATE jobs SET status='review',review_code=?,finished_at=? WHERE job_id=? AND status='running' AND attempt=?",
                (code, datetime.now(UTC).isoformat(), job_id, attempt),
            )
            if cursor.rowcount != 1:
                raise ValueError("attempt not running")
