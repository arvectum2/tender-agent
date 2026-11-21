"""Mac mini host admission for a reviewed daily index-only operator command.

This is not a source of authorization. The operator must use an approved
release and an explicitly admitted target. All host leases are nonblocking:
an existing daily/research batch is never stopped or forcibly unlocked.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import stat
import subprocess
import time
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

HOME = Path("/Users/master")
SAFE = HOME / "ArvectumSafe"
MI = SAFE / "worktrees/tender-agent-mi"
RESEARCH = SAFE / "worktrees/ta-fresh-compute-turn-20261120"
RESEARCH_SHA = "d632b81d269ac4f999dcaaf1e58cf8d1046693b1"
PYTHON = SAFE / ".venvs/tender-agent-mi/bin/python"
RESOURCE = SAFE / "runtime/ta-resource-governor"
RUNTIME = SAFE / "runtime/ta-source-discovery-20261114/autonomous-runner"
DEPLOY_LOCK = Path("/Volumes/ArvectumSSD/Arvectum/runtime/tender-agent/deploy.lock")
LIMITS = {"normal": 10, "reduced": 3, "paused": 0}


@contextmanager
def existing_lease(path: Path):
    """Never create, replace, or remove a cooperating lock."""
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        s = os.fstat(fd)
        if (
            not stat.S_ISREG(s.st_mode)
            or s.st_uid != os.getuid()
            or s.st_nlink != 1
            or s.st_mode & 0o022
        ):
            raise RuntimeError("unsafe existing recovery lease")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def resource_limit(path: Path = RESOURCE / "health.json"):
    if path.is_symlink():
        raise ValueError("unsafe resource telemetry")
    data = json.loads(path.read_text())
    age = datetime.now(UTC) - datetime.fromisoformat(data["checked_at_utc"])
    limit = LIMITS.get(data["mode"])
    if (
        data["schema"] != 1
        or data["status"] != "pass"
        or not timedelta(0) <= age <= timedelta(seconds=100)
        or type(data["batch_limit"]) is not int
        or limit != data["batch_limit"]
        or limit == 0
        or limit is None
    ):
        raise RuntimeError("host recovery resource admission denied")
    return limit


def checked_output(args, cwd, *, timeout=150):
    # No environment secrets, captured command output, or arbitrary shell code
    # are returned to the operator on failure.
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env={
            "HOME": str(HOME),
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        },
    )
    if result.returncode:
        raise RuntimeError("existing host verification command failed")
    return result.stdout


def checked_head(repo, expected=None):
    if repo.is_symlink() or repo.resolve() != repo:
        raise ValueError("unsafe host verification repository")
    if checked_output(
        ["/usr/bin/git", "status", "--porcelain"], repo, timeout=12
    ).strip():
        raise RuntimeError("host verification repository dirty")
    head = checked_output(
        ["/usr/bin/git", "rev-parse", "HEAD"], repo, timeout=12
    ).strip()
    if expected is not None and head != expected:
        raise RuntimeError("host verification revision changed")
    return head


def verified_prewrite():
    """Invoke the already deployed acceptance/PITR routines, not a bypass."""
    checked_head(RESEARCH, RESEARCH_SHA)
    mi_head = checked_head(MI)
    gate = json.loads(
        checked_output(
            [str(PYTHON), "-m", "scripts.market_intelligence.verify_internal_runtime"],
            MI,
        )
    )
    if (
        gate.get("status") != "pass"
        or gate.get("git_head") != mi_head
        or gate.get("postgresql_mutated_by_preflight") is not False
    ):
        raise RuntimeError("mandatory MI gate failed")
    # Reuse the installed archival compatibility proof contract. This is a
    # fixed, read-only invocation of the existing helper, not a new backup.
    expected = json.loads(
        checked_output(
            [
                str(PYTHON),
                "-c",
                (
                    "import json; from datetime import timedelta; "
                    "from scripts.research.target_backup_policy import recent_archived_backup; "
                    "print(json.dumps(recent_archived_backup(max_age=timedelta(hours=25))))"
                ),
            ],
            RESEARCH,
        )
    )
    if not expected or any(
        gate.get("backup", {}).get(k) != expected.get(k)
        for k in ("manifest", "sha256", "bytes")
    ):
        raise RuntimeError("verified archived compatibility backup missing or changed")
    proof = json.loads(
        checked_output([str(PYTHON), "-m", "scripts.research.dp_pitr_guard"], RESEARCH)
    )
    if proof.get("status") != "pass" or not all(
        proof.get(k) for k in ("point", "lsn", "base_manifest_sha256", "restore_proof")
    ):
        raise RuntimeError("mandatory PITR prewrite proof incomplete")
    return {
        "mi_head": mi_head,
        "backup_sha256": expected["sha256"],
        "restore_point": proof["point"],
        "restore_lsn": proof["lsn"],
        "base_manifest_sha256": proof["base_manifest_sha256"],
    }


def check_admission(runtime: Path):
    if DEPLOY_LOCK.exists() or (runtime / "STOP").exists():
        raise RuntimeError("maintenance or STOP prevents recovery")
    if shutil.disk_usage(runtime).free < 15 * 1024**3:
        raise RuntimeError("insufficient recovery disk headroom")
    return resource_limit()


@contextmanager
def wait_compute_lease(path, runtime, deadline):
    while True:
        check_admission(runtime)
        with ExitStack() as leases:
            try:
                leases.enter_context(existing_lease(path))
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise
            else:
                check_admission(runtime)
                yield
                return
        time.sleep(min(0.25, max(0, deadline - time.monotonic())))


@contextmanager
def admit_analysis_compute(*, wait_seconds=600):
    """Reserve a future compute turn without blocking historical commits.

    History probes the turn before taking its next heavy slot. The
    existing in-flight batch can finish; waiting analysis holds neither
    the historical priority nor mutation nor backup fence. Once acquired,
    the heavy lease alone protects the LLM generation.
    """
    if not 0 <= wait_seconds <= 600:
        raise ValueError("invalid compute lease wait")
    runtime = RUNTIME.resolve(strict=True)
    deadline = time.monotonic() + wait_seconds
    with ExitStack() as compute:
        with wait_compute_lease(
            RESOURCE / "fresh-compute-turn.lock", runtime, deadline
        ):
            compute.enter_context(
                wait_compute_lease(RESOURCE / "heavy-slot.lock", runtime, deadline)
            )
        check_admission(runtime)
        yield


@contextmanager
def _admit_write(runtime, *, prewrite, wait_seconds=0):
    # Retain neither priority nor mutation while waiting for a legacy writer.
    # A short bounded wait avoids discarding an already generated report.
    deadline = time.monotonic() + wait_seconds
    while True:
        limit = check_admission(runtime)
        with ExitStack() as leases:
            try:
                leases.enter_context(
                    existing_lease(runtime / "fresh-procurement-priority.lock")
                )
                leases.enter_context(existing_lease(runtime / "mutation.lock"))
                backup = ExitStack()
                leases.callback(backup.close)
                backup.enter_context(
                    existing_lease(runtime / "research-backup-gate.lock")
                )
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise
            else:
                with backup:
                    receipt = prewrite()
                if not isinstance(receipt, dict) or not all(
                    receipt.get(key)
                    for key in (
                        "mi_head",
                        "backup_sha256",
                        "restore_point",
                        "restore_lsn",
                        "base_manifest_sha256",
                    )
                ):
                    raise RuntimeError("missing accepted host prewrite receipt")
                yield min(limit, check_admission(runtime)), receipt
                return
        time.sleep(min(1, max(0, deadline - time.monotonic())))


@contextmanager
def admit_analysis_commit(*, prewrite=verified_prewrite, wait_seconds=120):
    """Caller holds analysis compute and daily/run leases; no LLM inside."""
    if not 0 <= wait_seconds <= 120:
        raise ValueError("invalid commit lease wait")
    with _admit_write(
        RUNTIME.resolve(strict=True), prewrite=prewrite, wait_seconds=wait_seconds
    ) as evidence:
        yield evidence


@contextmanager
def admit_index_batch(*, prewrite=verified_prewrite):
    """Preserve original heavyweight batch admission semantics."""
    runtime = RUNTIME.resolve(strict=True)
    check_admission(runtime)
    with (
        existing_lease(RESOURCE / "heavy-slot.lock"),
        _admit_write(runtime, prewrite=prewrite) as evidence,
    ):
        yield evidence
