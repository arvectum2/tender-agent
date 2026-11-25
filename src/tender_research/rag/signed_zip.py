"""Read bounded EIS signed office envelopes without altering originals."""

from __future__ import annotations

import hashlib
import io
import stat
import zipfile
from pathlib import Path

MAX_ENVELOPE = 32 * 1024**2
MAX_MEMBER = 24 * 1024**2
MAX_TOTAL = 48 * 1024**2
MAX_ENTRIES = 16
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def unwrap_signed_docx(path: Path, expected_sha256: str) -> tuple[bytes, dict]:
    """Legacy strict DOCX-only recovery contract."""
    content, evidence, _ = unwrap_signed_office(
        path, expected_sha256, extension=".docx", allow_pdf=False,
    )
    return content, evidence


def unwrap_signed_office(
    path: Path, expected_sha256: str, *, extension: str, allow_pdf: bool = True,
) -> tuple[bytes, dict, bytes | None]:
    """Verify envelope bytes and return office and optional separately bound PDF.

    A companion is not evidence of semantic equality or signature validity.
    """
    required_entries = {
        ".docx": {"[Content_Types].xml", "word/document.xml"},
        ".xlsx": {"[Content_Types].xml", "xl/workbook.xml"},
    }
    if extension not in required_entries:
        raise ValueError("unsupported signed ZIP office format")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ENVELOPE:
        raise ValueError("signed ZIP source missing or oversized")
    with path.open("rb") as stream:
        original = stream.read(MAX_ENVELOPE + 1)
    digest = hashlib.sha256(original).hexdigest()
    if len(original) > MAX_ENVELOPE or digest != expected_sha256:
        raise ValueError("signed ZIP source hash mismatch or oversized")
    try:
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            infos = archive.infolist()
            if not 2 <= len(infos) <= MAX_ENTRIES:
                raise ValueError("signed ZIP member count outside limit")
            seen = set()
            for info in infos:
                name = info.filename
                mode = stat.S_IFMT(info.external_attr >> 16)
                if (
                    not name
                    or len(name) > 1024
                    or any(ord(c) < 32 for c in name)
                    or any(c in name for c in "/\\:")
                    or name in {".", ".."}
                    or name != info.orig_filename
                    or info.is_dir()
                    or mode not in {0, stat.S_IFREG}
                    or info.flag_bits & 1
                    or name.casefold() in seen
                    or not 0 < info.file_size <= MAX_MEMBER
                    or info.file_size > max(1, info.compress_size) * 200
                ):
                    raise ValueError("unsafe signed ZIP member")
                seen.add(name.casefold())
            if sum(i.file_size for i in infos) > MAX_TOTAL:
                raise ValueError("signed ZIP expansion limit exceeded")
            documents = [i for i in infos if i.filename.lower().endswith(extension)]
            if len(documents) != 1:
                raise ValueError("signed ZIP must contain exactly one expected office member")
            document = documents[0]
            companions = [
                i for i in infos if i.filename.casefold() == document.filename.casefold() + ".pdf"
            ] if allow_pdf else []
            if len(companions) > 1:
                raise ValueError("ambiguous signed ZIP PDF companion")
            signatures = [i for i in infos if i is not document and i not in companions]
            if not signatures or any(
                not i.filename.casefold().startswith(document.filename.casefold())
                or Path(i.filename).suffix.lower() not in {".sig", ".sign", ".p7s"}
                for i in signatures
            ):
                raise ValueError("unexpected content in signed office ZIP")

            def read(info):
                with archive.open(info) as member:
                    data = member.read(info.file_size + 1)
                if len(data) != info.file_size:
                    raise ValueError("signed ZIP member size mismatch")
                return data

            content = read(document)
            with zipfile.ZipFile(io.BytesIO(content)) as office:
                names = office.namelist()
                if len(names) != len(set(names)) or not required_entries[extension] <= set(names):
                    raise ValueError("inner file is not an unambiguous office document")
                if (
                    len(names) > 2048
                    or sum(i.file_size for i in office.infolist()) > 100 * 1024**2
                ):
                    raise ValueError("inner office document exceeds safety budget")
            evidence = {
                "archive_sha256": digest,
                "member_name": document.filename,
                "member_sha256": hashlib.sha256(content).hexdigest(),
                "member_size": len(content),
                "signatures": [
                    {
                        "name": i.filename,
                        "sha256": hashlib.sha256(read(i)).hexdigest(),
                        "size": i.file_size,
                    }
                    for i in signatures
                ],
                "signature_verification": "not_performed",
            }
            pdf = None
            if companions:
                companion = companions[0]
                pdf = read(companion)
                if not pdf.startswith(b"%PDF-"):
                    raise ValueError("signed ZIP companion is not a PDF")
                evidence["pdf_companion"] = {
                    "member_name": companion.filename,
                    "member_sha256": hashlib.sha256(pdf).hexdigest(),
                    "member_size": len(pdf),
                    "semantic_equivalence": "not_verified",
                }
            return content, evidence, pdf
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError) as exc:
        raise ValueError("signed ZIP cannot be decoded safely") from exc
