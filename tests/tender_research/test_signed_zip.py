import hashlib
import io
import stat
import zipfile

import pytest

from src.tender_research.rag.signed_zip import unwrap_signed_docx


def package(members):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in members:
            archive.writestr(name, data)
    return output.getvalue()


DOC = package(
    [("[Content_Types].xml", b"<Types/>"), ("word/document.xml", b"<document/>")]
)
GOOD = [("test.docx", DOC), ("test.docx_author.sig", b"signature")]


def write(tmp_path, members):
    path = tmp_path / "test.docx.zip"
    raw = package(members)
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


def test_signed_envelope_preserves_original(tmp_path):
    p, digest = write(tmp_path, GOOD)
    result, evidence = unwrap_signed_docx(p, digest)
    assert result == DOC
    assert evidence["archive_sha256"] == digest
    assert evidence["member_sha256"] == hashlib.sha256(DOC).hexdigest()
    assert (
        evidence["signatures"][0]["sha256"] == hashlib.sha256(b"signature").hexdigest()
    )
    assert evidence["signature_verification"] == "not_performed"
    assert hashlib.sha256(p.read_bytes()).hexdigest() == digest
    assert list(tmp_path.iterdir()) == [p]


@pytest.mark.parametrize(
    "members",
    [
        [("test.docx", DOC)],
        GOOD + [("other.docx", DOC)],
        GOOD + [("../evil.sig", b"x")],
        GOOD + [("TEST.DOCX_AUTHOR.SIG", b"x")],
        [("test.docx", DOC), ("unknown.sig", b"x")],
        [("test.docx", b"not a docx"), ("test.docx.sig", b"x")],
    ],
)
def test_ambiguous_or_unsafe_archive_refused(tmp_path, members):
    p, digest = write(tmp_path, members)
    with pytest.raises(ValueError):
        unwrap_signed_docx(p, digest)


def test_hash_and_symlink_refused(tmp_path):
    p, digest = write(tmp_path, GOOD)
    with pytest.raises(ValueError):
        unwrap_signed_docx(p, "0" * 64)
    link = tmp_path / "link.docx.zip"
    link.symlink_to(p)
    with pytest.raises(ValueError):
        unwrap_signed_docx(link, digest)


def test_special_file_refused(tmp_path):
    info = zipfile.ZipInfo("test.docx_author.sig")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    p, digest = write(tmp_path, [("test.docx", DOC), (info, b"target")])
    with pytest.raises(ValueError):
        unwrap_signed_docx(p, digest)


@pytest.mark.parametrize("extension,inner_path", [
    (".docx", "word/document.xml"),
    (".xlsx", "xl/workbook.xml"),
])
def test_office_with_pdf_and_signature_distinct_evidence(tmp_path, extension, inner_path):
    from src.tender_research.rag.signed_zip import unwrap_signed_office

    office = package([("[Content_Types].xml", b"<Types/>"), (inner_path, b"<root/>")])
    name = "test" + extension
    pdf = b"%PDF-1.7\nsynthetic"
    p, digest = write(tmp_path, [(name, office), (name + ".sig", b"sig"), (name + ".pdf", pdf)])
    result, evidence, companion = unwrap_signed_office(p, digest, extension=extension)
    assert result == office and companion == pdf
    assert evidence["archive_sha256"] == digest
    assert evidence["member_sha256"] == hashlib.sha256(office).hexdigest()
    assert evidence["pdf_companion"]["member_sha256"] == hashlib.sha256(pdf).hexdigest()
    assert evidence["pdf_companion"]["semantic_equivalence"] == "not_verified"
    assert evidence["signature_verification"] == "not_performed"
    assert len(evidence["signatures"]) == 1
    assert hashlib.sha256(p.read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("members", [
    GOOD + [("other.pdf", b"%PDF-1.7")],
    GOOD + [("test.docx.pdf", b"not PDF")],
    GOOD + [("test.docx.pdf", b"%PDF-1.7"), ("other.xlsx", b"x")],
    [("test.docx", DOC), ("test.docx.pdf", b"%PDF-1.7")],
    GOOD + [("test.docx.pdf", b"%PDF-1.7"), ("TEST.DOCX.PDF", b"%PDF-1.7")],
])
def test_office_envelope_rejects_unbound_or_unverified_members(tmp_path, members):
    from src.tender_research.rag.signed_zip import unwrap_signed_office

    p, digest = write(tmp_path, members)
    with pytest.raises(ValueError):
        unwrap_signed_office(p, digest, extension=".docx")


def test_legacy_docx_only_recovery_does_not_silently_expand_scope(tmp_path):
    p, digest = write(tmp_path, GOOD + [("test.docx.pdf", b"%PDF-1.7")])
    with pytest.raises(ValueError):
        unwrap_signed_docx(p, digest)
