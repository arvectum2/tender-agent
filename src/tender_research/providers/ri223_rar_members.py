"""Fail-closed RAR5/RAR4 member streaming for source-bound public RI223 attachments.

External libarchive bsdtar performs decompression in a subprocess; archive contents
are never extracted into their own filesystem paths or executed. The individual
accepted document bytes are bounded before persistence / Data Platform processing.
"""
from __future__ import annotations

import os
import re
import select
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ALLOWED_MEMBER_EXTENSIONS = frozenset({".pdf", ".doc", ".docx", ".xlsx", ".xls", ".txt", ".csv", ".xml"})
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 24 * 1024 * 1024
MAX_TOTAL_BYTES = 120 * 1024 * 1024
MAX_ENTRIES = 128
MAX_EXPANSION_RATIO = 200
LIST_TIMEOUT_SECONDS = 20
MEMBER_TIMEOUT_SECONDS = 25


class Ri223RarError(ValueError):
    """RAR cannot be safely and fully projected to ordinary documents."""


@dataclass(frozen=True)
class Ri223RarMember:
    path: str
    filename: str
    content: bytes


def is_ri223_rar_document(document) -> bool:
    meta = getattr(document, "raw_meta", None)
    evidence = meta.get("evidence") if isinstance(meta, dict) else None
    return (
        str(getattr(document, "file_name", "")).lower().endswith(".rar")
        and isinstance(meta, dict) and meta.get("source_regime") == "223fz"
        and isinstance(evidence, dict)
        and evidence.get("regime") == "223fz"
        and evidence.get("source") == "RI223_getDocsIP"
        and bool(re.fullmatch(r"[a-f0-9]{64}", str(evidence.get("archive_sha256", ""))))
        and bool(re.fullmatch(r"[a-f0-9]{64}", str(evidence.get("xml_sha256", ""))))
    )


def _safe_member_path(value: str) -> PurePosixPath:
    if not value or len(value) > 1024 or any(ord(c) < 32 for c in value):
        raise Ri223RarError("RAR contains invalid member name")
    if "\\" in value or "//" in value or "/./" in value or value.startswith("./") or re.match(r"^[A-Za-z]:", value):
        raise Ri223RarError("RAR contains unsafe Windows member path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise Ri223RarError("RAR member path escapes archive root")
    if len(path.parts) > 8:
        raise Ri223RarError("RAR nesting exceeds depth limit")
    return path


def _run_listing(args: list[str]) -> list[str]:
    try:
        outcome = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", timeout=LIST_TIMEOUT_SECONDS,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise Ri223RarError("RAR listing failed or timed out") from exc
    if len(outcome.stdout) > 256_000:
        raise Ri223RarError("RAR listing too large")
    return outcome.stdout.splitlines()


def _stream_member(archive: Path, name: str, expected_bytes: int) -> bytes:
    try:
        proc = subprocess.Popen(
            ["bsdtar", "-xOf", str(archive), "--", name],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        raise Ri223RarError("RAR streaming backend unavailable") from exc
    assert proc.stdout is not None
    deadline = time.monotonic() + MEMBER_TIMEOUT_SECONDS
    data = bytearray()
    try:
        while True:
            wait = deadline - time.monotonic()
            if wait <= 0:
                raise Ri223RarError("RAR member streaming timed out")
            if not select.select([proc.stdout], [], [], wait)[0]:
                raise Ri223RarError("RAR member streaming timed out")
            chunk = os.read(proc.stdout.fileno(), 64 * 1024)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_MEMBER_BYTES or len(data) > expected_bytes:
                raise Ri223RarError("RAR member exceeds declared size or safety limit")
        if proc.wait(timeout=max(0.1, deadline - time.monotonic())) != 0:
            raise Ri223RarError("RAR member decompression failed")
        if len(data) != expected_bytes:
            raise Ri223RarError("RAR member size mismatch")
        return bytes(data)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        proc.stdout.close()


def extract_ri223_rar_members(archive: Path) -> tuple[Ri223RarMember, ...]:
    """Read supported regular members or refuse the entire archive.

    Requires libarchive's bsdtar executable. There is intentionally no fallback
    to blind shell extraction, sandbox mutation or optimistic partial success.
    """
    archive = Path(archive).resolve()
    if not archive.is_file() or archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise Ri223RarError("RAR missing or exceeds compressed size budget")
    with archive.open("rb") as reader:
        signature = reader.read(8)
    if not signature.startswith((b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00")):
        raise Ri223RarError("Invalid RAR4/RAR5 signature")
    if not shutil.which("bsdtar"):
        raise Ri223RarError("libarchive bsdtar unavailable; manual review required")
    names = _run_listing(["bsdtar", "-tf", str(archive)])
    verbose = _run_listing(["bsdtar", "-tvf", str(archive)])
    if len(names) != len(verbose) or len(names) > MAX_ENTRIES or not names:
        raise Ri223RarError("RAR member count or listing mismatch")

    accepted: list[tuple[str, int]] = []
    seen: set[str] = set()
    expanded_total = 0
    for path_string, metadata in zip(names, verbose, strict=True):
        parsed = _safe_member_path(path_string.rstrip("/"))
        mode = metadata[:1]
        if mode == "d":
            continue
        if mode != "-":
            raise Ri223RarError("RAR special files/links are forbidden")
        if path_string in seen:
            raise Ri223RarError("Duplicate RAR member path")
        seen.add(path_string)
        tokens = metadata.split(maxsplit=5)
        if len(tokens) < 6 or not tokens[4].isdigit():
            raise Ri223RarError("Cannot validate declared RAR member size")
        size = int(tokens[4])
        expanded_total += size
        if size > MAX_MEMBER_BYTES or expanded_total > MAX_TOTAL_BYTES:
            raise Ri223RarError("RAR decompressed size limit exceeded")
        if parsed.suffix.lower() not in ALLOWED_MEMBER_EXTENSIONS:
            raise Ri223RarError("RAR has unsupported inner document format")
        accepted.append((path_string, size))

    if expanded_total > max(1, archive.stat().st_size) * MAX_EXPANSION_RATIO:
        raise Ri223RarError("RAR compression ratio exceeds safety limit")
    if not accepted:
        raise Ri223RarError("RAR contains no supported regular documents")

    return tuple(
        Ri223RarMember(path=name, filename=PurePosixPath(name).name,
                       content=_stream_member(archive, name, size))
        for name, size in accepted
    )
