"""Fail-closed OFFLINE examination of already-registered EIS deadline snapshots.

This is NOT a current EIS revision proof. It never fetches sources, modifies
DailyTenderRunItem.deadline_at or creates source/archive files.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.modules.daily_tender_run.eis_detail_deadline import (
    MAX_HTML_BYTES,
    REGISTRY_RE,
    EISProofError,
    _official_url,
    parse_official_detail,
)

SHA_RE = re.compile(r"^[a-f0-9]{64}$")
RAW_NAME = "public_detail_common_info.html"


class ArchivedDeadlineError(ValueError):
    """Intentionally does not expose source bytes, paths, or untrusted metadata."""


@dataclass(frozen=True)
class ArchivedDeadline:
    registry_number: str
    archived_deadline_utc: datetime
    official_timezone: str
    artifact_sha256: str
    artifact_registered_utc: datetime
    source_status: str = "ARCHIVED_ONLY"
    current_revision_verified: bool = False


def _trusted_snapshot_bytes(root: Path, registry: str, expected_size: int) -> bytes:
    if not root.is_absolute() or root.is_symlink():
        raise ArchivedDeadlineError("archive_unverified")
    case = root / registry
    raw = case / "raw"
    file = raw / RAW_NAME
    if any(p.is_symlink() for p in (case, raw, file)):
        raise ArchivedDeadlineError("archive_unverified")
    if not (root.is_dir() and case.is_dir() and raw.is_dir()):
        raise ArchivedDeadlineError("archive_unverified")
    for directory in (root, case, raw):
        st = directory.stat()
        if st.st_uid != os.getuid() or st.st_mode & 0o022:
            raise ArchivedDeadlineError("archive_unverified")
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(file, flags)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode)
                or st.st_uid != os.getuid()
                or st.st_nlink != 1
                or st.st_mode & 0o022
                or st.st_size != expected_size):
            raise ArchivedDeadlineError("archive_unverified")
        data = os.read(fd, expected_size + 1)
        if len(data) != expected_size:
            raise ArchivedDeadlineError("archive_unverified")
        return data
    finally:
        os.close(fd)


def verify_archived_deadline(
    root: Path,
    registry_number: str,
    artifact: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> ArchivedDeadline:
    """Verify stored DB artifact + on-disk bytes. Never claims live freshness."""
    try:
        if not isinstance(registry_number, str) or not REGISTRY_RE.fullmatch(registry_number):
            raise ArchivedDeadlineError("archive_unverified")
        if (artifact["registry_number"] != registry_number
                or artifact["law_type"] != "44fz"
                or artifact["artifact_type"] != "public_detail_common_info"
                or artifact["source"] != "external_public_44fz"):
            raise ArchivedDeadlineError("archive_unverified")
        meta = artifact["raw_meta"]
        if not isinstance(meta, dict) or meta.get("registry_number") != registry_number:
            raise ArchivedDeadlineError("archive_unverified")
        _official_url(meta.get("card_url"), registry_number)
        _official_url(meta.get("source_url"), registry_number)
        if not isinstance(root, Path):
            raise ArchivedDeadlineError("archive_unverified")
        expected_file = root / registry_number / "raw" / RAW_NAME
        if artifact.get("local_path") != str(expected_file):
            raise ArchivedDeadlineError("archive_unverified")
        size = artifact["size_bytes"]
        digest = artifact["sha256"]
        if (type(size) is not int or not 0 < size <= MAX_HTML_BYTES
                or not isinstance(digest, str) or not SHA_RE.fullmatch(digest)):
            raise ArchivedDeadlineError("archive_unverified")
        registered = artifact["created_at"]
        clock = now if now is not None else datetime.now(UTC)
        if (not isinstance(registered, datetime) or registered.tzinfo is None
                or registered.utcoffset() is None
                or clock.tzinfo is None or clock.utcoffset() is None
                or registered > clock):
            raise ArchivedDeadlineError("archive_unverified")
        data = _trusted_snapshot_bytes(root, registry_number, size)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ArchivedDeadlineError("archive_unverified")
        exact, zone = parse_official_detail(data.decode("utf-8", "strict"), registry_number)
        return ArchivedDeadline(
            registry_number=registry_number,
            archived_deadline_utc=exact,
            official_timezone=zone,
            artifact_sha256=digest,
            artifact_registered_utc=registered.astimezone(UTC),
        )
    except (OSError, KeyError, TypeError, ValueError, UnicodeError, EISProofError) as exc:
        raise ArchivedDeadlineError("archive_unverified") from exc
