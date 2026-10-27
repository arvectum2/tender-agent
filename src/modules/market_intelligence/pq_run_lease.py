"""Short-lived cooperative lease for ARC/ChatGPT hourly research runs.

A stale lease is recoverable, but expiry never authorizes killing a process.
Uses atomic mkdir on a shared filesystem; each lease has a unique owner token.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Lease:
    path: Path
    owner: str


def _metadata(path: Path) -> dict:
    try:
        return json.loads((path / "owner.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def acquire(path: Path, *, ttl_seconds: int = 300, now: float | None = None) -> Lease | None:
    if not 60 <= ttl_seconds <= 900:
        raise ValueError("Lease TTL outside safe bounds")
    current = time.time() if now is None else now
    owner = secrets.token_hex(16)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.mkdir()
    except FileExistsError:
        return None
    metadata = {"owner": owner, "host": socket.gethostname(),
                "acquired_at": current, "heartbeat_at": current,
                "expires_at": current + ttl_seconds, "pid": os.getpid()}
    try:
        (path / "owner.json").write_text(json.dumps(metadata), encoding="utf-8")
    except BaseException:
        shutil.rmtree(path)
        raise
    return Lease(path, owner)


def renew(lease: Lease, *, ttl_seconds: int = 300, now: float | None = None) -> bool:
    if not 60 <= ttl_seconds <= 900:
        raise ValueError("Lease TTL outside safe bounds")
    current = time.time() if now is None else now
    data = _metadata(lease.path)
    if data.get("owner") != lease.owner or data.get("expires_at", 0) <= current:
        return False
    data["heartbeat_at"] = current
    data["expires_at"] = current + ttl_seconds
    temp = lease.path / ("owner-" + lease.owner + ".tmp")
    temp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(temp, lease.path / "owner.json")
    return True


def release(lease: Lease) -> bool:
    if _metadata(lease.path).get("owner") != lease.owner:
        return False
    (lease.path / "owner.json").unlink()
    lease.path.rmdir()
    return True


def inspect(path: Path, *, now: float | None = None) -> dict:
    current = time.time() if now is None else now
    if not path.exists():
        return {"status": "free"}
    data = _metadata(path)
    if not data:
        return {"status": "unreadable", "requires_reconciliation": True}
    return {"status": "expired" if data.get("expires_at", 0) <= current else "held",
            "owner": data.get("owner"), "host": data.get("host"),
            "pid": data.get("pid"), "expires_at": data.get("expires_at"),
            "requires_reconciliation": data.get("expires_at", 0) <= current}
