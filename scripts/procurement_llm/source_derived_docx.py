"""Reproducible, content-verified DOCX derived from pinned procurement originals."""
from __future__ import annotations

import hashlib
import io
import stat
from pathlib import Path
from zipfile import BadZipFile, ZipFile, ZipInfo

MAX_DERIVED_DOCX = 450_000
MAX_EXPANDED = 7_000_000
NORMALIZED_TIME = (1980, 1, 1, 0, 0, 0)


def _payload(original: bytes) -> list[tuple[ZipInfo, bytes]]:
    if not 0 < len(original) <= MAX_DERIVED_DOCX:
        raise ValueError("derived DOCX must be bounded")
    try:
        with ZipFile(io.BytesIO(original)) as archive:
            infos = archive.infolist()
            if not 1 <= len(infos) <= 100 or sum(i.file_size for i in infos) > MAX_EXPANDED:
                raise ValueError("derived DOCX inflated size/entry count unsafe")
            if len({i.filename for i in infos}) != len(infos):
                raise ValueError("derived DOCX duplicate members")
            if any(
                info.is_dir() or info.filename.startswith("/") or ".." in info.filename.split("/")
                for info in infos
            ):
                raise ValueError("derived DOCX contains unsafe members")
            result = [(info, archive.read(info)) for info in infos]
    except BadZipFile as exc:
        raise ValueError("derived DOCX invalid ZIP") from exc
    if not any(i.filename == "word/document.xml" for i, _ in result):
        raise ValueError("not an OOXML Word document")
    return result


def canonical_docx_bytes(docx_bytes: bytes) -> bytes:
    """Stable SHA: normalize ZIP timestamps/extra metadata, not document content."""
    entries = _payload(docx_bytes)
    out = io.BytesIO()
    with ZipFile(out, "w") as archive:
        for source, data in entries:
            info = ZipInfo(source.filename, date_time=NORMALIZED_TIME)
            info.compress_type = source.compress_type
            info.external_attr = source.external_attr
            info.internal_attr = source.internal_attr
            info.create_system = source.create_system
            info.flag_bits = source.flag_bits
            archive.writestr(info, data)
    result = out.getvalue()
    if len(result) > MAX_DERIVED_DOCX:
        raise ValueError("derived DOCX canonical output oversized")
    return result


def same_docx_content(left: bytes, right: bytes) -> bool:
    """Accept older time-stamped generated files only when ALL member bytes match."""
    return [
        (info.filename, data) for info, data in _payload(left)
    ] == [
        (info.filename, data) for info, data in _payload(right)
    ]



def reuse_existing_verified_source_document(
    tender, document_id: str, expected_binary: bytes,
    expected_receipt: dict, private_directory: Path,
) -> tuple[str, str] | None:
    """Strictly reuse legacy DOCX physical SHA where packaging alone changed.

    The row's immutable source identity and actual SHA stay unchanged. Never
    mutate document rows, silently replace provenance or rewrite a real file.
    """
    matches = [
        doc for doc in tender.documents
        if doc.source_document_id == document_id
    ]
    if len(matches) > 1:
        raise ValueError("duplicate stable derived document identity")
    if not matches:
        return None
    doc = matches[0]
    source = Path(doc.local_path) if doc.local_path else None
    if (
        source is None or source.is_symlink() or not source.is_file()
        or source.parent.resolve() != private_directory.resolve()
        or stat.S_IMODE(source.stat().st_mode) != 0o600
        or not isinstance(doc.raw_meta, dict)
    ):
        raise ValueError("existing derived source document path unsafe")
    existing = source.read_bytes()
    original_sha = hashlib.sha256(existing).hexdigest()
    if (
        doc.sha256 != original_sha
        or doc.raw_meta.get("derived_docx_sha256") != original_sha
        or not same_docx_content(existing, expected_binary)
        or any(
            key != "derived_docx_sha256" and doc.raw_meta.get(key) != value
            for key, value in expected_receipt.items()
        )
    ):
        raise ValueError("existing source derived document provenance or content conflict")
    return str(source), original_sha
