"""APR-06 offline source integrity: real bytes, not trust in supplied SHA strings.

This module NEVER proves that files came from EIS, represent the latest notice,
or have been approved by a human. It only verifies content against an existing
frozen manifest and always reports official provenance as NOT_VERIFIED.
"""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from src.modules.commercial_acceptance.acceptance import (
    AcceptanceError,
    HASH_PATTERN,
    validate_manifest,
)

MAX_FILE_BYTES = 256 * 1024 * 1024


def _regular_file_hash(path: Path, *, size_limit: int = MAX_FILE_BYTES) -> str:
    """Digest local bytes without following a final symlink or trusting a name."""
    if path.is_symlink() or not path.is_file():
        raise AcceptanceError(f"Missing, symlinked or non-regular original: {path.name}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise AcceptanceError(f"Cannot securely open original: {path.name}") from exc
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size < 1 or info.st_size > size_limit:
            raise AcceptanceError(f"Original empty, non-regular or oversized: {path.name}")
        digest = hashlib.sha256()
        total = 0
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            total += len(chunk)
            if total > size_limit:
                raise AcceptanceError(f"Original exceeded size limit: {path.name}")
            digest.update(chunk)
        if total != info.st_size:
            raise AcceptanceError(f"Original size changed during read: {path.name}")
    return digest.hexdigest()


def _safe_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise AcceptanceError(f"Source directory absent or symlinked: {path.name}")


def verify_offline_bytes(manifest: dict, source_root: Path) -> dict:
    """Match notice.bin and SHA-addressed attachments to a FROZEN manifest.

    Expected layout (supplied by a trusted evidence collector, not this code):
      root/REG_NUMBER/notice.bin
      root/REG_NUMBER/attachments/SHA256_HEX

    A successful result is never sufficient for commercial ACCEPTED: a false
    manifest plus matching invented bytes can still pass local hash checking.
    Official notice identity, revision, file completeness and expert approvals
    require independent source receipts and human checks.
    """
    info = validate_manifest(manifest, require_frozen=True)
    _safe_directory(source_root)
    checked_files = 0
    checked_bytes = 0
    for case in manifest["cases"]:
        reg = case["reg_number"]
        verification = case["verification"]
        case_dir = source_root / reg
        attachment_dir = case_dir / "attachments"
        _safe_directory(case_dir)
        _safe_directory(attachment_dir)
        expected_notice = verification["notice_sha256"]
        if not HASH_PATTERN.fullmatch(expected_notice):
            raise AcceptanceError(f"{reg}: malformed notice digest")
        notice = case_dir / "notice.bin"
        actual_notice = _regular_file_hash(notice)
        if actual_notice != expected_notice:
            raise AcceptanceError(f"{reg}: original notice byte digest mismatch")
        checked_files += 1
        checked_bytes += notice.stat().st_size
        hashes = verification["document_sha256"]
        if len(hashes) != len(set(hashes)):
            raise AcceptanceError(f"{reg}: duplicate attachment digests")
        for expected in hashes:
            if not HASH_PATTERN.fullmatch(expected):
                raise AcceptanceError(f"{reg}: malformed attachment digest")
            path = attachment_dir / expected
            actual = _regular_file_hash(path)
            if actual != expected:
                raise AcceptanceError(f"{reg}: attachment byte digest mismatch")
            checked_files += 1
            checked_bytes += path.stat().st_size
    return {
        "schema_version": "apr06-local-bytes-v1",
        "status": "BYTES_MATCH_MANIFEST_ORIGIN_UNVERIFIED",
        "cases_checked": info["count"],
        "files_checked": checked_files,
        "bytes_checked": checked_bytes,
        "official_eis_provenance_verified": False,
        "current_notice_revision_verified": False,
        "attachment_set_completeness_verified": False,
        "human_expert_review_verified": False,
        "commercial_acceptance": "BLOCKED_OFFICIAL_SOURCE_AND_HUMAN_REVIEW",
    }
