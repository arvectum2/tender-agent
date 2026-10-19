"""Reproducible, content-verified DOCX derived from pinned procurement originals."""
from __future__ import annotations

import io
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
