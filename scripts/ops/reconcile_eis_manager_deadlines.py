"""Owner-gated, source-rechecked 37-manager EIS deadline correction.

Two phases: first-party read-only prepare; then pinned-production guarded dry-run
and explicitly authorized commit. No bulk 298 updates, statuses, bids or restarts.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import fcntl
import hashlib
import importlib.util
import json
import os
import threading
import time
import urllib.error
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

SNAPSHOT_SHA = "47cae7aea67ded3c39af1cc0fd2808d9abf2af441fa3233605780d2ab28a1d27"
CSV_SHA = "c36168601f6b7b949002287d78363ad40bcfa3103cdd587466838e25353e2d3a"
EXPECTED_PIN = Path(
    "/Volumes/ArvectumSSD/Arvectum/releases/"
    "tender-agent-9b650a2b818032389cfd6e13799acad33c72089b/source"
)
DB_IDENTITY = ("arvectum", "arvectum", "127_private_review_link_corrections")
MAX_SOURCE_AGE = timedelta(minutes=75)


class SourceMismatch(ValueError):
    pass


def _audit():
    path = Path(__file__).resolve().parents[1] / "diagnostics" / "audit_eis_midnight_deadlines.py"
    spec = importlib.util.spec_from_file_location("eis_source_proof", path)
    if spec is None or spec.loader is None:
        raise SourceMismatch("official EIS original parser unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MAX_HTML = 6_000_000
    return module


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _private_dir(path: Path, create: bool = False) -> None:
    if path.is_symlink():
        raise SourceMismatch("unsafe symlink folder")
    if create and not path.exists():
        path.mkdir(parents=False, mode=0o700)
    if not path.is_dir() or path.stat().st_mode & 0o077:
        raise SourceMismatch("unsafe private evidence directory")


def _exclusive_file(path: Path, content: bytes) -> str:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as target:
        target.write(content)
        target.flush()
        os.fsync(target.fileno())
    return _hash(content)


def _json_write_once(path: Path, value: dict) -> str:
    return _exclusive_file(
        path, (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    )


def _load_source(audit_root: Path, now: datetime) -> tuple[list[dict], object]:
    audit = _audit()
    snapshot = audit_root / "snapshot.json"
    if not snapshot.is_file() or _hash(snapshot.read_bytes()) != SNAPSHOT_SHA:
        raise SourceMismatch("the immutable original 298-row DB snapshot SHA changed")
    data, groups = audit._read_snapshot(snapshot, SNAPSHOT_SHA)
    csv_path = audit_root / "EIS_298_ALL_VERIFIED.csv"
    if not csv_path.is_file() or _hash(csv_path.read_bytes()) != CSV_SHA:
        raise SourceMismatch("the immutable 298-row source comparison CSV SHA changed")
    with csv_path.open(encoding="utf-8", newline="") as stream:
        observed = list(csv.DictReader(stream))
    if len(observed) != 298:
        raise SourceMismatch("not exactly 298 audited source rows")
    originals = {r["id"]: r for group in groups.values() for r in group}
    candidates = []
    for row in observed:
        orig = originals.get(row["record_id"])
        if (orig is None or row["registry_number"] != orig["registry_number"]
                or row["run_id"] != orig["run_id"]
                or row["status"] != orig["status"]
                or row["source_url"] != orig["source_url"]
                or row["stored_utc"] != orig["deadline_at"]):
            raise SourceMismatch("public audit CSV differs from pinned DB snapshot")
        if row["status"] != "MANAGER_READY" or datetime.fromisoformat(row["official_utc"]) <= now:
            continue
        official = datetime.fromisoformat(row["official_utc"])
        stored = datetime.fromisoformat(row["stored_utc"])
        changed = official != stored
        candidates.append({
            "id": orig["id"], "registry_number": orig["registry_number"],
            "run_id": orig["run_id"], "status": "MANAGER_READY",
            "source": orig["source"], "source_url": orig["source_url"],
            "source_fingerprint": orig["source_fingerprint"],
            "stage": orig["stage"],
            "old_deadline_utc": stored.isoformat(),
            "new_deadline_utc": official.isoformat(),
            "old_updated_at": orig["updated_at"],
            "audit_html_sha256": row["source_sha256"],
            "changed": changed,
        })
    counts = Counter(r["changed"] for r in candidates)
    if (len(candidates) != 37
            or len({r["id"] for r in candidates}) != 37
            or len({r["registry_number"] for r in candidates}) != 37
            or counts != {True: 35, False: 2}):
        raise SourceMismatch("37 unique future manager rows / 35 changes / 2 noops not proven")
    # Original audited receipts and HTML must bind every candidate to a real first-party source.
    for r in candidates:
        registry = r["registry_number"]
        source_path = audit_root / "html" / (registry + ".html")
        receipt_path = audit_root / "receipts" / (registry + ".json")
        if (source_path.is_symlink() or receipt_path.is_symlink()
                or not source_path.is_file() or not receipt_path.is_file()):
            raise SourceMismatch("original EIS source or receipt absent")
        raw = source_path.read_bytes()
        receipt = json.loads(receipt_path.read_text())
        parsed = audit.extract_exact_eis_deadline(raw.decode("utf-8", "replace"), registry)
        if (receipt.get("source_html_sha256") != _hash(raw)
                or _hash(raw) != r["audit_html_sha256"]
                or parsed["official_utc"] != r["new_deadline_utc"]
                or receipt.get("status") != "official_exact_verified"
                or receipt.get("official_utc") != r["new_deadline_utc"]):
            raise SourceMismatch("original official evidence no longer proves target deadline")
    return (sorted(candidates, key=lambda x: x["registry_number"]), audit,
            data["metadata"]["db_system_id_sha256"])


def prepare(audit_root: Path, root: Path, now: datetime) -> dict:
    if root.exists() or root.is_symlink():
        raise SourceMismatch("new private reconciliation root already exists")
    rows, audit, system_hash = _load_source(audit_root, now)
    _private_dir(root, True)
    html_dir = root / "official-recheck-html"
    _private_dir(html_dir, True)
    fd = os.open(root / ".single-flight.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pace = threading.Lock()
        last = [0.0]

        def fetch(row: dict) -> tuple[str, dict]:
            registry = row["registry_number"]
            audit._unique_notice_url(row["source_url"], registry)
            with pace:
                delay = 0.88 - (time.monotonic() - last[0])
                if delay > 0:
                    time.sleep(delay)
                last[0] = time.monotonic()
            p = audit._fetch(row["source_url"], registry)
            raw = p["raw"]
            official = audit.extract_exact_eis_deadline(raw.decode("utf8", "replace"), registry)
            if official["official_utc"] != row["new_deadline_utc"]:
                raise SourceMismatch(f"official source deadline changed after audit for {registry}")
            _exclusive_file(html_dir / (registry + ".html"), raw)
            return registry, {
                **official,
                "registry_number": registry,
                "html_sha256": _hash(raw), "html_bytes": len(raw),
                "official_url": row["source_url"],
                "checked_at_utc": datetime.now(UTC).isoformat(),
            }

        results = []
        failures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            future_map = {pool.submit(fetch, r): r["registry_number"] for r in rows}
            for f in concurrent.futures.as_completed(future_map):
                try:
                    results.append(f.result())
                except (SourceMismatch, OSError, ValueError, urllib.error.URLError) as exc:
                    failures.append({"registry": future_map[f], "error": type(exc).__name__})
        if failures or len(results) != 37:
            _json_write_once(root / "blocked-source-rechecks.json", {
                "checked": len(results), "failures": failures,
            })
            raise SourceMismatch(f"{len(failures)} live official notice rechecks failed; no plan")
        evidence = dict(results)
        if set(evidence) != {r["registry_number"] for r in rows}:
            raise SourceMismatch("fresh source identities missing")
        plan = {
            "task_id": "TA-EIS-MANAGER-DEADLINES-20261123",
            "created_at_utc": datetime.now(UTC).isoformat(),
            "original_audit_snapshot_sha256": SNAPSHOT_SHA,
            "original_audit_csv_sha256": CSV_SHA,
            "expected_db": list(DB_IDENTITY),
            "expected_db_system_sha256": system_hash,
            "rows": rows,
            "fresh_eis_rechecks": evidence,
            "rows_checked": 37,
            "rows_to_update": 35,
            "rows_already_exact": 2,
            "authorized": "user instruction делать source-verified manager-ready correction",
        }
        sha = _json_write_once(root / "plan.json", plan)
        _exclusive_file(root / "plan.sha256", (sha + "\n").encode())
        return {"status": "prepared", "checked": 37, "updates": 35, "noop": 2,
                "plan_sha256": sha, "source_verified": 37}
    finally:
        os.close(fd)


def _load_prepared(root: Path, expected_sha: str, *, require_fresh: bool = True) -> dict:
    _private_dir(root)
    p = root / "plan.json"
    if p.is_symlink() or not p.is_file() or _hash(p.read_bytes()) != expected_sha:
        raise SourceMismatch("reconciliation manifest SHA mismatch")
    if (root / "plan.sha256").read_text().strip() != expected_sha:
        raise SourceMismatch("manifest published proof changed")
    plan = json.loads(p.read_text())
    if (plan.get("task_id") != "TA-EIS-MANAGER-DEADLINES-20261123"
            or plan.get("expected_db") != list(DB_IDENTITY)
            or plan.get("original_audit_snapshot_sha256") != SNAPSHOT_SHA
            or plan.get("original_audit_csv_sha256") != CSV_SHA
            or plan.get("rows_checked") != 37 or plan.get("rows_to_update") != 35
            or plan.get("rows_already_exact") != 2
            or len(plan.get("rows", [])) != 37):
        raise SourceMismatch("invalid prepared manifest identity/scope")
    orig_snap = root.parent / "eis-midnight-audit-20261123" / "snapshot.json"
    if not orig_snap.is_file() or _hash(orig_snap.read_bytes()) != SNAPSHOT_SHA:
        raise SourceMismatch("original production snapshot was replaced")
    original_sys = json.loads(orig_snap.read_text())["metadata"]["db_system_id_sha256"]
    if (plan.get("expected_db_system_sha256") != original_sys
            or len(original_sys) != 64):
        raise SourceMismatch("prepared PostgreSQL system identity does not match original")
    if (require_fresh and datetime.now(UTC) - datetime.fromisoformat(plan["created_at_utc"])
            > MAX_SOURCE_AGE):
        raise SourceMismatch("fresh source attestation expired")
    audit = _audit()
    for row in plan["rows"]:
        registry = row["registry_number"]
        proof = plan["fresh_eis_rechecks"][registry]
        source = root / "official-recheck-html" / (registry + ".html")
        if source.is_symlink() or not source.is_file():
            raise SourceMismatch("fresh official HTML missing")
        raw = source.read_bytes()
        parsed = audit.extract_exact_eis_deadline(raw.decode("utf8", "replace"), registry)
        audit._unique_notice_url(row["source_url"], registry)
        if (_hash(raw) != proof["html_sha256"]
                or len(raw) != proof["html_bytes"]
                or parsed["official_utc"] != row["new_deadline_utc"]
                or proof["official_utc"] != row["new_deadline_utc"]):
            raise SourceMismatch("fresh official original/manifest mismatch")
    return plan


def _db():
    import src.shared.db.session as db_session

    if not Path(db_session.__file__).resolve().is_relative_to(EXPECTED_PIN.resolve()):
        raise SourceMismatch("not connected through trusted pinned release module")
    return db_session.engine


def _check_db_rows(connection, plan: dict, lock: bool) -> list[dict]:
    from sqlalchemy import bindparam, text

    identity = connection.execute(text(
        "SELECT current_database(), current_user, "
        "(SELECT version_num FROM alembic_version), "
        "(SELECT system_identifier::text FROM pg_control_system())"
    )).one()
    if tuple(identity[:3]) != DB_IDENTITY:
        raise SourceMismatch("production DB identity mismatch")
    system_sha = _hash(identity[3].encode())
    expected_snapshot_system_sha = plan["expected_db_system_sha256"]
    # Source identity hash is verified against the canonical original snapshot,
    # not a guessed database name or temporary Docker/test database.
    if system_sha != expected_snapshot_system_sha:
        raise SourceMismatch("unexpected PostgreSQL system identifier")
    if connection.execute(text("SELECT pg_is_in_recovery()")).scalar_one():
        raise SourceMismatch("standby database cannot be altered")
    ids = [r["id"] for r in plan["rows"]]
    query = text(
        "SELECT id::text AS id, registry_number, run_id, status, stage, source, "
        "source_url, source_fingerprint, deadline_at, updated_at "
        "FROM daily_tender_run_items WHERE id::text IN :ids"
        + (" FOR UPDATE NOWAIT" if lock else "")
    ).bindparams(bindparam("ids", expanding=True))
    rows = [dict(r) for r in connection.execute(query, {"ids": ids}).mappings()]
    if len(rows) != 37:
        raise SourceMismatch("expected exactly 37 existing MANAGER_READY row IDs")
    byid = {r["id"]: r for r in rows}
    for source in plan["rows"]:
        cur = byid[source["id"]]
        keys = ("registry_number", "run_id", "status", "stage",
                "source", "source_url", "source_fingerprint")
        if any(cur[k] != source[k] for k in keys):
            raise SourceMismatch(f"original DB business identity changed for {source['id']}")
        if (cur["deadline_at"].astimezone(UTC) !=
                datetime.fromisoformat(source["old_deadline_utc"])
                or cur["updated_at"].astimezone(UTC) !=
                datetime.fromisoformat(source["old_updated_at"])):
            raise SourceMismatch(f"concurrent timestamp edit for {source['id']}")
    return rows


def _serialize_db_rows(rows: list[dict]) -> list[dict]:
    return [
        {k: (v.astimezone(UTC).isoformat() if isinstance(v, datetime) else v)
         for k, v in row.items()}
        for row in sorted(rows, key=lambda r: r["id"])
    ]


def transact(root: Path, expected_sha: str, *, commit: bool) -> dict:
    from sqlalchemy import text

    plan = _load_prepared(root, expected_sha)
    lock = root / ".single-flight.lock"
    fd = os.open(lock, os.O_RDWR | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        engine = _db()
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                conn.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
                conn.execute(text("SET LOCAL statement_timeout = '12000ms'"))
                conn.execute(text("SET LOCAL lock_timeout = '2500ms'"))
                before = _check_db_rows(conn, plan, lock=True)
                # Ensure only the 35 expected rows can be modified. Keep
                # the exact old values and per-row source proof for rollback.
                if commit:
                    _json_write_once(root / "db-before.json", {
                        "plan_sha256": expected_sha, "identity": list(DB_IDENTITY),
                        "records": _serialize_db_rows(before),
                        "backup_at_utc": datetime.now(UTC).isoformat(),
                    })
                updated = []
                for source in plan["rows"]:
                    if not source["changed"]:
                        continue
                    statement = text(
                        "UPDATE daily_tender_run_items SET deadline_at = :new_deadline, "
                        "updated_at = NOW() WHERE id = CAST(:id AS uuid) "
                        "AND registry_number = :registry AND run_id = :run_id "
                        "AND status = 'MANAGER_READY' "
                        "AND source = 'public_eis_html_44fz' "
                        "AND source_url = :source_url "
                        "AND source_fingerprint = :fingerprint "
                        "AND deadline_at = :old_deadline "
                        "AND updated_at = :old_updated "
                        "RETURNING id::text AS id, deadline_at, updated_at"
                    )
                    result = conn.execute(statement, {
                        "id": source["id"], "registry": source["registry_number"],
                        "run_id": source["run_id"],
                        "source_url": source["source_url"],
                        "fingerprint": source["source_fingerprint"],
                        "new_deadline": datetime.fromisoformat(source["new_deadline_utc"]),
                        "old_deadline": datetime.fromisoformat(source["old_deadline_utc"]),
                        "old_updated": datetime.fromisoformat(source["old_updated_at"]),
                    }).mappings().all()
                    if len(result) != 1:
                        raise SourceMismatch(f"not exactly one conditional row {source['id']}")
                    got = result[0]
                    if (got["id"] != source["id"]
                            or got["deadline_at"].astimezone(UTC) !=
                            datetime.fromisoformat(source["new_deadline_utc"])):
                        raise SourceMismatch("unexpected DB timestamp after conditional update")
                    updated.append(source["id"])
                if len(updated) != 35:
                    raise SourceMismatch("expected precisely 35 conditional UPDATE returns")
                if commit:
                    _json_write_once(root / "commit-intent.json", {
                        "plan_sha256": expected_sha,
                        "updated_row_ids": updated,
                        "old_row_backup": "db-before.json",
                        "sent_at_utc": datetime.now(UTC).isoformat(),
                    })
                    tx.commit()
                else:
                    tx.rollback()
            except BaseException:
                if tx.is_active:
                    tx.rollback()
                raise
        if commit:
            receipt = verify_postcommit(root, expected_sha)
            _json_write_once(root / "commit-verified.json", receipt)
            return receipt
        return {"status": "dry_run_rolled_back", "conditional_updates_tested": 35,
                "rows_unchanged": 37, "source_sha256": expected_sha}
    finally:
        os.close(fd)


def verify_postcommit(root: Path, expected_sha: str) -> dict:
    from sqlalchemy import text

    plan = _load_prepared(root, expected_sha, require_fresh=False)
    audit_root = root.parent / "eis-midnight-audit-20261123"
    audit = _audit()
    _, grouped = audit._read_snapshot(audit_root / "snapshot.json", SNAPSHOT_SHA)
    expected = {x["id"]: x for group in grouped.values() for x in group}
    targets = {x["id"]: x for x in plan["rows"]}
    engine = _db()
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            conn.execute(text("SET LOCAL statement_timeout = '10000ms'"))
            rows = conn.execute(text(
                "SELECT id::text AS id, registry_number, run_id, status, "
                "source, source_url, source_fingerprint, deadline_at "
                "FROM daily_tender_run_items"
            )).mappings().all()
            if len(rows) != 299:
                raise SourceMismatch("full DB 299 row verification failed")
            changed = 0
            unchanged = 0
            max_verified = 0
            for row in rows:
                if row["id"] in expected:
                    old = expected[row["id"]]
                    if any(row[k] != old[k] for k in (
                            "registry_number", "run_id", "status", "source",
                            "source_url", "source_fingerprint")):
                        raise SourceMismatch("post-commit business identity changed")
                    original = datetime.fromisoformat(old["deadline_at"])
                    if row["id"] in targets and targets[row["id"]]["changed"]:
                        target = datetime.fromisoformat(
                            targets[row["id"]]["new_deadline_utc"]
                        )
                        if row["deadline_at"].astimezone(UTC) != target:
                            raise SourceMismatch("target did not persist official EIS time")
                        changed += 1
                    else:
                        if row["deadline_at"].astimezone(UTC) != original:
                            raise SourceMismatch("collateral historical deadline modification")
                        unchanged += 1
                else:
                    if (row["registry_number"] != "0845500000526000021"
                            or row["deadline_at"].astimezone(UTC) !=
                            datetime(2026, 11, 30, 6, 0, tzinfo=UTC)):
                        raise SourceMismatch("prior MAX source-verified correction changed")
                    max_verified += 1
            if (changed, unchanged, max_verified) != (35, 263, 1):
                raise SourceMismatch("full 299 row reconciliation failed")
            tx.rollback()
            return {
                "status": "commit_verified", "rows_updated": 35,
                "other_audited_rows_unchanged": 263,
                "total_db_rows": 299, "prior_max_corrected_untouched": True,
                "source_rechecks": 37, "plan_sha256": expected_sha,
                "verified_at_utc": datetime.now(UTC).isoformat(),
                "submitted_bids": 0, "service_restarts": 0,
            }
        except BaseException:
            if tx.is_active:
                tx.rollback()
            raise


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("prepare", "dry-run", "commit", "verify"))
    p.add_argument("--audit-root", required=True, type=Path)
    p.add_argument("--out-root", required=True, type=Path)
    p.add_argument("--expected-plan-sha256", default="")
    args = p.parse_args()
    if args.mode == "prepare":
        outcome = prepare(args.audit_root, args.out_root, datetime.now(UTC))
    elif args.mode == "verify":
        outcome = verify_postcommit(args.out_root, args.expected_plan_sha256)
    else:
        outcome = transact(
            args.out_root, args.expected_plan_sha256, commit=args.mode == "commit"
        )
    print(json.dumps(outcome, ensure_ascii=False))


if __name__ == "__main__":
    main()
