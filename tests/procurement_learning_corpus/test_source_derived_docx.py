"""Canonical normalized DOCX bytes and backwards-safe content attestation."""
from __future__ import annotations

import io
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from docx import Document

from scripts.procurement_llm.source_derived_docx import (
    canonical_docx_bytes,
    same_docx_content,
)


def _docx(sentence="Проверенный источник ЕИС") -> bytes:
    d = Document()
    d.add_paragraph(sentence)
    data = io.BytesIO()
    d.save(data)
    return data.getvalue()


def _repack_with_new_timestamp(payload: bytes, year: int) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(io.BytesIO(payload)) as original, ZipFile(buffer, "w") as result:
        for old in original.infolist():
            info=ZipInfo(old.filename, date_time=(year, 5, 7, 11, 13, 14))
            info.compress_type=ZIP_DEFLATED
            result.writestr(info,original.read(old.filename))
    return buffer.getvalue()


def test_derived_docx_byte_sha_not_affected_by_zip_member_timestamps():
    raw=_docx()
    with_old=_repack_with_new_timestamp(raw,2000)
    with_new=_repack_with_new_timestamp(raw,2026)
    assert with_old != with_new
    assert same_docx_content(with_old,with_new)
    assert canonical_docx_bytes(with_old) == canonical_docx_bytes(with_new)
    assert canonical_docx_bytes(canonical_docx_bytes(with_old)) == canonical_docx_bytes(with_old)


def test_derived_docx_modification_rejected_even_if_name_unchanged():
    a=_docx("Источник: вес 30%")
    b=_docx("Источник: вес 90%")
    assert not same_docx_content(a,b)


def test_untrusted_archive_members_are_rejected():
    f=io.BytesIO()
    with ZipFile(f,"w") as archive:
        archive.writestr("../word/document.xml",b"<attack/>")
    with pytest.raises(ValueError):
        canonical_docx_bytes(f.getvalue())


def test_untrusted_non_zip_rejected():
    with pytest.raises(ValueError):
        canonical_docx_bytes(b"invalid")
