"""Opt-in product-owned internal procurement endpoint.

A separately reviewed local manifest, exact release/DB binding and dedicated
bearer are required. No Basic-auth bypass, generic credentials, or source writes.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .workspace_reference import ReferenceDenied, ReferenceScope, read_internal_procurement

PATH = "/api/internal/workspace/procurement-reference"
DRAFT = "9c0f7caa552613ab598d9de05b819524a74e8c73"
SCHEMA = "arvectum.tender.internal-procurement-access/1"
MAX_EXPIRY = datetime.fromisoformat("2026-12-17T09:35:36.060836+00:00")


def _private(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path:
        raise ReferenceDenied("unsafe manifest path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        s = os.fstat(f.fileno())
        if s.st_uid != os.getuid() or not stat.S_ISREG(s.st_mode) or s.st_mode & 0o077 or s.st_nlink != 1:
            raise ReferenceDenied("unsafe manifest")
        raw = f.read(8193)
    if len(raw) > 8192:
        raise ReferenceDenied("manifest too large")
    return raw


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _matches(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def load_scope(path, pin, release, auth, clock):
    if not _matches(pin, r"[a-f0-9]{64}") or not _matches(release, r"[a-f0-9]{40}"):
        raise ReferenceDenied("deployment pins required")
    raw = _private(path)
    if not hmac.compare_digest(_sha(raw), pin):
        raise ReferenceDenied("manifest pin mismatch")
    d = json.loads(raw)
    if not isinstance(d, dict) or set(d) != {
        "schema", "draft_blob", "binding_id", "source_release", "database_binding",
        "deal_ids", "starts_at", "expires_at", "token_sha256",
    } or d["schema"] != SCHEMA or d["draft_blob"] != DRAFT or d["source_release"] != release:
        raise ReferenceDenied("manifest mismatch")
    if (not _matches(d["token_sha256"], r"[a-f0-9]{64}")
        or not _matches(auth, r"Bearer [a-f0-9]{64}")
        or not hmac.compare_digest(_sha(auth[7:].encode("ascii")), d["token_sha256"])):
        raise ReferenceDenied("credential denied")
    ids = d["deal_ids"]
    if not isinstance(ids, list) or not 1 <= len(ids) <= 21 or any(
        not _matches(i, r"DL-[A-Za-z0-9-]{1,60}") for i in ids
    ) or len(set(ids)) != len(ids):
        raise ReferenceDenied("invalid identity set")
    start, end = (datetime.fromisoformat(d[k]) for k in ("starts_at", "expires_at"))
    if start.utcoffset() != timezone.utc.utcoffset(start) or end.utcoffset() != timezone.utc.utcoffset(end):
        raise ReferenceDenied("UTC interval required")
    if not start <= clock() < end <= MAX_EXPIRY:
        raise ReferenceDenied("expired source admission")
    if not _matches(d["database_binding"], r"[a-f0-9]{64}") or not _matches(d["binding_id"], r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}"):
        raise ReferenceDenied("invalid source identity")
    return ReferenceScope(d["binding_id"], release, d["database_binding"], frozenset(ids), start, end)


def database_binding(session):
    """Pin actual PostgreSQL cluster, database and role, not a URL or secret.

    If pg_control_system is not available to the product role, fail closed.
    Do not elevate permissions merely to satisfy this check.
    """
    row = session.execute(text("""
        SELECT current_database(),current_user,
               (SELECT oid::text FROM pg_database WHERE datname=current_database()),
               system_identifier::text
        FROM pg_control_system()
    """)).one()
    return _sha(json.dumps(list(row), separators=(",", ":")).encode())


def read_from_postgres(engine, scope, authorize, clock):
    if engine.dialect.name != "postgresql":
        raise ReferenceDenied("PostgreSQL source required")
    with Session(engine, autoflush=False, expire_on_commit=False) as session:
        with session.begin():
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            if session.execute(text("SHOW transaction_read_only")).scalar_one() != "on":
                raise ReferenceDenied("read-only transaction required")
            if database_binding(session) != scope.database_binding:
                raise ReferenceDenied("database binding mismatch")
            result = read_internal_procurement(session, scope=scope, authorize=authorize, clock=clock)
            # Explicit rollback even though all queries were read-only.
            session.rollback()
            return result


def install_workspace_reference(app: FastAPI, *, engine, path=None, pin=None, release=None,
                                reader=read_from_postgres, clock=lambda: datetime.now(timezone.utc)):
    """Production wiring passes existing product engine, no caller-controlled target."""
    @app.get(PATH, include_in_schema=False)
    def read(request: Request):
        if not path or not pin or not release:
            raise HTTPException(503, "SOURCE_NOT_ADMITTED")
        if (request.client is None or request.client.host != "127.0.0.1"
            or request.headers.get("host") != "127.0.0.1:8001"
            or request.url.query or request.headers.get("content-length", "0") != "0"
            or request.headers.get("transfer-encoding")
            or any(h in request.headers for h in ("origin", "referer", "cookie", "forwarded",
                "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "x-real-ip"))):
            raise HTTPException(403, "SOURCE_ACCESS_DENIED")
        def authorize():
            return load_scope(path, pin, release, request.headers.get("authorization"), clock)
        try:
            scope = authorize()
            result = reader(engine, scope, authorize, clock)
            if authorize() != scope:
                raise ReferenceDenied("source permission changed")
        except (ReferenceDenied, OSError, TypeError, ValueError, KeyError, AttributeError, RecursionError):
            raise HTTPException(403, "SOURCE_ACCESS_DENIED") from None
        except Exception:
            # Never expose SQL, credentials or private paths in a response.
            raise HTTPException(503, "SOURCE_UNAVAILABLE") from None
        return JSONResponse(result, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
