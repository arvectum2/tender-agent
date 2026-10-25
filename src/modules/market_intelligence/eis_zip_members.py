"""Source-hash-linked, one-level ZIP member staging for official EIS annexes.

Only safe, bounded PDF/DOC/DOCX/XLSX/XLS/PPTX/RTF members are staged for
Data Platform ingestion. 7z, RAR and nested ZIP are retained in the parent
ZIP for separate explicit review, never extracted or indexed as text.
"""

from __future__ import annotations

import hashlib
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

MAX_ZIP_BYTES = 160 * 1024 * 1024
MAX_MEMBERS = 300
MAX_SINGLE_MEMBER_BYTES = 48 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 256 * 1024 * 1024
ALLOWED_EXTRACTABLE = frozenset({".pdf", ".doc", ".docx", ".xls", ".xlsx", ".pptx", ".rtf", ".txt"})
OPAQUE = frozenset({".zip", ".rar", ".7z"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stage_official_zip_children(
    archive_path: Path,
    *,
    expected_parent_sha256: str,
    target_dir: Path,
    max_members: int = 100,
    max_total_bytes: int = 96 * 1024 * 1024,
) -> dict[str, object]:
    if (not re.fullmatch(r"[a-f0-9]{64}", expected_parent_sha256)
            or not 1 <= max_members <= MAX_MEMBERS
            or not 1 <= max_total_bytes <= MAX_TOTAL_UNCOMPRESSED):
        raise ValueError("Invalid ZIP integrity or resource limit")
    if (archive_path.is_symlink()
            or not archive_path.is_file()
            or archive_path.stat().st_size > MAX_ZIP_BYTES
            or _sha256(archive_path) != expected_parent_sha256):
        raise ValueError("Original ZIP parent SHA or path invalid")
    if target_dir.is_symlink():
        raise ValueError("ZIP staging directory cannot be symlink")
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target_dir.chmod(0o700)
    records: list[dict[str, object]] = []
    staged_bytes = 0
    with zipfile.ZipFile(archive_path) as container:
        members = container.infolist()
        if len(members) > max_members:
            raise ValueError("ZIP exceeds entry budget")
        if sum(info.file_size for info in members) > MAX_TOTAL_UNCOMPRESSED:
            raise ValueError("ZIP exceeds declared total uncompressed budget")
        for member in members:
            if member.is_dir():
                continue
            name = member.filename
            path = PurePosixPath(name.replace("\\", "/"))
            # Reject unsafe ZIP entries, symlinks, ZIP bombs and oversized
            # entries *before* reading or writing a single child.
            if (name.startswith(("/", "\\"))
                    or any(part in ("..", "", ".") for part in path.parts)
                    or path.is_absolute()
                    or re.match(r"^[A-Za-z]:", name)
                    or stat.S_ISLNK(member.external_attr >> 16)
                    or member.flag_bits & 1):
                raise ValueError("Unsafe or encrypted ZIP member")
            if member.file_size > MAX_SINGLE_MEMBER_BYTES:
                raise ValueError("ZIP member exceeds resource limit")
            if member.compress_size == 0 and member.file_size > 0:
                raise ValueError("Suspicious ZIP compression")
            if member.compress_size and member.file_size > member.compress_size * 250:
                raise ValueError("Potential ZIP bomb compression ratio")
            extension = path.suffix.lower()
            kind = ("stage" if extension in ALLOWED_EXTRACTABLE
                    else "opaque" if extension in OPAQUE else "unsupported")
            if kind == "stage":
                if member.file_size + staged_bytes > max_total_bytes:
                    raise ValueError("Staging budget exceeded")
                payload = container.read(member)
                if len(payload) != member.file_size:
                    raise ValueError("Original member incomplete")
                document_sha = hashlib.sha256(payload).hexdigest()
                member_path_sha = hashlib.sha256(name.encode("utf-8")).hexdigest()
                stored_name = f"eis-{expected_parent_sha256[:12]}-{member_path_sha[:16]}{extension}"
                candidate = target_dir / stored_name
                if candidate.is_symlink():
                    raise ValueError("Existing staged child is symlinked")
                if candidate.exists():
                    if _sha256(candidate) != document_sha:
                        raise ValueError("Existing original member changed; inspect provenance")
                else:
                    with candidate.open("xb") as output:
                        output.write(payload)
                    candidate.chmod(0o600)
                staged_bytes += len(payload)
                status = "staged_sha256_verified_not_yet_indexed"
            else:
                document_sha = None
                member_path_sha = hashlib.sha256(name.encode("utf-8")).hexdigest()
                stored_name = None
                status = "opaque_unparsed" if kind == "opaque" else "unsupported_unparsed"
            records.append({
                "original_parent_zip_sha256": expected_parent_sha256,
                "original_member_path_sha256": member_path_sha,
                "member_extension": extension,
                "member_size_bytes": member.file_size,
                "member_sha256": document_sha,
                "local_stored_name": stored_name,
                "status": status,
                "data_platform_indexed": False,
            })
    return {
        "schema_version": "mi-eis-official-zip-children/0.1",
        "original_parent_zip_sha256": expected_parent_sha256,
        "listed_members": len(records),
        "staged_members": sum(record["status"] == "staged_sha256_verified_not_yet_indexed" for record in records),
        "unparsed_opaque_members": sum(record["status"] == "opaque_unparsed" for record in records),
        "staged_total_bytes": staged_bytes,
        "records": records,
    }
