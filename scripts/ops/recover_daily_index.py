"""Single-collection index repair, explicitly admitted active release only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import stat
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

LAUNCHER = Path("/Users/master/arvectum-ops/arv-075/scripts/daily-tender-ssd.sh")
JOURNAL_ROOT = Path(
    "/Volumes/ArvectumSSD/Arvectum/private/tender-agent/daily-index-recovery"
)
SYSTEM_ID = "7692004809331994662"


def identity_digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def private_directory(path):
    s = path.lstat()
    if (
        path.resolve() != path
        or not stat.S_ISDIR(s.st_mode)
        or s.st_uid != os.getuid()
        or s.st_mode & 0o077
    ):
        raise RuntimeError("unsafe recovery journal directory")


def pending_journal(root, registry):
    for path in root.glob(registry + "-*.jsonl"):
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
            or info.st_size > 1_000_000
        ):
            raise RuntimeError("unsafe recovery journal")
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if not rows or rows[-1].get("event") != "verified_batch":
            raise RuntimeError("previous attempt requires independent reconciliation")


@contextmanager
def journal(root, registry, payload):
    root.mkdir(mode=0o700, exist_ok=True)
    private_directory(root)
    pending_journal(root, registry)
    path = root / (registry + "-" + uuid4().hex + ".jsonl")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

        def record(event, data):
            f.write(
                json.dumps(
                    {"at": datetime.now(UTC).isoformat(), "event": event, "data": data}
                )
                + chr(10)
            )
            f.flush()
            os.fsync(f.fileno())

        record("admitted", payload)
        try:
            yield record
        except BaseException:
            record("requires_review", {"reason": "attempt_not_verified"})
            raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("run", "registry", "deal", "fingerprint"):
        p.add_argument("--" + key, required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm-release")
    p.add_argument("--expected-identity-sha")
    args = p.parse_args()
    daily = runpy.run_path(str(LAUNCHER))
    release = daily["RELEASE"]
    if (
        Path(__file__).resolve().parents[2] != release / "source"
        or Path(sys.prefix).resolve() != (release / "venv").resolve()
    ):
        raise RuntimeError("run from approved active release")
    if args.apply and (
        args.confirm_release != daily["SHA"] or not args.expected_identity_sha
    ):
        raise ValueError("exact release and plan confirmation required")
    fd = None
    try:
        if args.apply:
            fd = daily["acquire_daily_lock"]()
        env = daily["preflight"]()
        os.environ.clear()
        os.environ.update(env)
        os.chdir("/Users/master")
        return execute(args, daily["SHA"])
    finally:
        if fd is not None:
            os.close(fd)


def execute(args, release_sha):
    from dataclasses import asdict

    from sqlalchemy import create_engine, text

    from scripts.ops.daily_index_recovery_host import admit_index_batch
    from src.modules.daily_tender_run.index_reconciliation import (
        reconcile,
        repair_absent_batch,
    )
    from src.modules.daily_tender_run.index_snapshot import PostgresIndexReader
    from src.modules.daily_tender_run.recovery_plan import RecoveryTarget, plan_target
    from src.shared.db import models as _models  # noqa: F401
    from src.shared.db.session import SessionLocal, engine
    from src.tender_research.config import load_config
    from src.tender_research.rag.data_platform import build_data_platform_client
    from src.tender_research.repository import TenderRepository

    target = RecoveryTarget(args.run, args.registry, args.deal, args.fingerprint)
    platform = create_engine(engine.url.set(database="arvectum_data"))
    reader = PostgresIndexReader(platform, SYSTEM_ID)
    try:
        with SessionLocal() as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            repo = TenderRepository(session)

            def scope():
                session.expire_all()
                current = plan_target(session, target)
                if (
                    current["status"] != "candidate_for_reviewed_recovery"
                    or not current["collection_id"]
                ):
                    raise RuntimeError("target no longer eligible")
                chunks = repo.list_chunks_by_tender(current["tender_id"])
                snapshot = reader(current["collection_id"])
                payload = {
                    "release": release_sha,
                    "target": asdict(target),
                    "tender_id": current["tender_id"],
                    "collection_id": current["collection_id"],
                    "contract": asdict(snapshot.contract),
                    "chunks": sorted(
                        (str(c.id), hashlib.sha256(c.text.encode()).hexdigest())
                        for c in chunks
                    ),
                }
                return current, snapshot, chunks, identity_digest(payload)

            current, snapshot, chunks, digest = scope()
            plan = reconcile(chunks, list(snapshot.rows), snapshot.contract)
            if not args.apply:
                print(
                    json.dumps(
                        {
                            "status": "read_only",
                            "target": asdict(target),
                            "collection_id": snapshot.collection_id,
                            "identity_sha256": digest,
                            "counts": plan["counts"],
                            "complete": plan["complete"],
                            "requires_review": plan["requires_review"],
                        },
                        indent=2,
                    )
                )
                return 0
            if digest != args.expected_identity_sha or plan["requires_review"]:
                raise RuntimeError("requested scope or persisted evidence changed")
            if JOURNAL_ROOT.exists():
                private_directory(JOURNAL_ROOT)
                pending_journal(JOURNAL_ROOT, target.registry_number)
            if plan["complete"]:
                print(
                    json.dumps(
                        {"status": "already_complete", "identity_sha256": digest}
                    )
                )
                return 0
            config = load_config()
            config.rag_data_platform_timeout_seconds = max(
                config.rag_data_platform_timeout_seconds, 180
            )
            with admit_index_batch() as (limit, receipt):
                if scope()[3] != digest:
                    raise RuntimeError("scope changed after admission")
                with journal(
                    JOURNAL_ROOT,
                    target.registry_number,
                    {"identity_sha256": digest, "prewrite": receipt, "limit": limit},
                ) as record:
                    with build_data_platform_client(config) as client:

                        def verify_snapshot(cid):
                            _, s, _, now = scope()
                            if now != digest or s.collection_id != cid:
                                raise RuntimeError("scope changed during recovery")
                            return s

                        class JournalClient:
                            def ingest_chunk(self, **params):
                                record(
                                    "ingest_requested",
                                    {"chunk_id": str(params["chunk_id"])},
                                )
                                response = client.ingest_chunk(**params)
                                record(
                                    "ingest_response",
                                    {"chunk_id": str(params["chunk_id"])},
                                )
                                return response

                        @contextmanager
                        def granted():
                            yield limit

                        result = repair_absent_batch(
                            repo=repo,
                            client=JournalClient(),
                            tender_id=current["tender_id"],
                            collection_id=snapshot.collection_id,
                            expected_contract=snapshot.contract,
                            read_snapshot=verify_snapshot,
                            admitted_write=granted,
                            limit=limit,
                        )
                    record("verified_batch", result)
                print(json.dumps(result))
            session.rollback()
            return 0
    finally:
        platform.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
