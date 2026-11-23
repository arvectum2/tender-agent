"""Mac mini owner-private guarded runtime for unified procurement pipeline.

No second scheduler or database. Existing Docker PostgreSQL is dumped and
validated BEFORE any new canonical DB write. A single non-blocking file lock
prevents overlapping manual/watchdog starts. All receipts owner-private 0600.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from scripts.procurement_llm.collect_public_market_originals import OWNER_PRIVATE

BACKUP_MAX_BYTES = 100 * 1024 * 1024


class PipelineRuntimeError(RuntimeError):
    """Cannot safely issue a canonical source write."""


def _owner_dir(root: Path, name: str) -> Path:
    if root.is_symlink() or not root.is_dir():
        raise PipelineRuntimeError("owner-private ArvectumSSD mount not available")
    p = root / name
    if p.is_symlink():
        raise PipelineRuntimeError("owner-private symlink forbidden")
    p.mkdir(mode=0o700, exist_ok=True)
    if p.stat().st_mode & 0o077:
        raise PipelineRuntimeError("private directory must not be readable by others")
    return p


@contextmanager
def single_runner(root: Path = OWNER_PRIVATE):
    folder = _owner_dir(root, "intake-runs")
    lock = folder / "unified-source-pipeline.lock"
    if lock.is_symlink():
        raise PipelineRuntimeError("unsafe pipeline lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.fstat(fd).st_mode & 0o077:
            raise PipelineRuntimeError("pipeline lock permissions unsafe")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PipelineRuntimeError("another source pipeline cycle still active") from exc
        yield
    finally:
        os.close(fd)


def _run_docker(command: list[str], *, input_bytes: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            command, input=input_bytes, capture_output=True,
            timeout=120, check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PipelineRuntimeError("existing PostgreSQL backup/catalogue command failed") from exc
    return result.stdout


def fresh_pg_backup(root: Path = OWNER_PRIVATE) -> dict:
    folder = _owner_dir(root, "backups")
    now = datetime.now(UTC)
    raw = _run_docker([
        "docker", "exec", "arvectum-postgres", "pg_dump",
        "-U", "arvectum", "-d", "arvectum",
        "--format=custom", "--no-owner", "--no-acl", "--compress=6",
    ])
    if not 1024 < len(raw) <= BACKUP_MAX_BYTES or not raw.startswith(b"PGDMP"):
        raise PipelineRuntimeError("pg_dump is missing/oversized/not custom-format")
    catalogue = _run_docker(
        ["docker", "exec", "-i", "arvectum-postgres", "pg_restore", "--list"],
        input_bytes=raw,
    )
    if (b"TABLE DATA public procurement_learning_observations" not in catalogue
            or b"TABLE public procurement_learning_observations" not in catalogue):
        raise PipelineRuntimeError("cannot verify source-learning table in restore catalogue")
    digest = hashlib.sha256(raw).hexdigest()
    path = folder / (now.strftime("arvectum-source-intake-%Y%m%dT%H%M%S%fZ-")
                     + digest[:16] + ".dump")
    with NamedTemporaryFile(
        mode="wb", dir=folder, prefix=".pg-prewrite-", suffix=".part",
        delete=False,
    ) as file:
        temp_path = Path(file.name)
        try:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
    try:
        if path.exists():
            raise PipelineRuntimeError("cannot overwrite immutable prewrite backup")
        os.replace(temp_path, path)
        os.chmod(path, 0o600)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise PipelineRuntimeError("prewrite backup disk hash mismatch")
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return {
        "backed_up_existing_database": "arvectum",
        "sha256": digest,
        "bytes": len(raw),
        "private_backup_path": str(path),
        "restore_catalogue_verified": True,
        "restored_live_database": False,
    }


def save_private_receipt(report: dict, root: Path = OWNER_PRIVATE) -> Path:
    folder = _owner_dir(root, "intake-runs")
    if not isinstance(report, dict) or report.get("schema") != "arvectum_daily_source_pipeline_receipt_v1":
        raise PipelineRuntimeError("unrecognized pipeline receipt")
    # Only bounded metadata. Never serialize auth query, EIS token or HTML.
    body = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    if len(body) > 100_000 or b"docRequestUid" in body or b"compoundUid" in body:
        raise PipelineRuntimeError("receipt may contain sensitive transport query")
    digest = hashlib.sha256(body).hexdigest()
    observed = report.get("observed_at_utc", "")
    if not isinstance(observed, str) or not re.fullmatch(r"[0-9T:+.Z-]{19,40}", observed):
        raise PipelineRuntimeError("invalid receipt timestamp")
    out = folder / (
        datetime.now(UTC).strftime("source-intake-%Y%m%dT%H%M%S%fZ-")
        + digest[:16] + ".json"
    )
    fd = os.open(out, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(body)
            file.flush()
            os.fsync(file.fileno())
    except BaseException:
        out.unlink(missing_ok=True)
        raise
    return out
