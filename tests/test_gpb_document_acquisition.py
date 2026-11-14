import io
import zipfile

from scripts.research.acquire_gpb_documents import valid_bytes


def test_capture_only_archive_signatures():
    assert valid_bytes(b"Rar!\x1a\x07\x01", ".rar")
    assert valid_bytes(b"7z\xbc\xaf\x27\x1c", ".7z")
    assert valid_bytes(b"PK\x03\x04", ".zip")
    assert not valid_bytes(b"<html>Denied</html>", ".zip")
    assert not valid_bytes(b"MZ", ".exe")


def test_ooxml_requires_expected_structure():
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as z:
        z.writestr("word/document.xml", "<document/>")
    assert valid_bytes(raw.getvalue(), ".docx")
    assert not valid_bytes(raw.getvalue(), ".xlsx")


def test_pdf_requires_eof():
    assert valid_bytes(b"%PDF-1.7\n%%EOF", ".pdf")
    assert not valid_bytes(b"%PDF-1.7", ".pdf")


def test_equal_content_keeps_prior_source_receipts():
    import pytest

    from scripts.research.link_gpb_document_receipts import reconcile_capture_metadata

    base = {"source": "etp_gpb", "capture_status": "verified_private_original", "dp_index": None}
    prior = {**base, "capture_receipt": {"document_url": "a"}}
    new = {**base, "capture_receipts": [{"document_url": "a"}, {"document_url": "b"}]}
    assert reconcile_capture_metadata(prior, new)
    assert not reconcile_capture_metadata(new, new)
    with pytest.raises(ValueError, match="removed or changed"):
        reconcile_capture_metadata(new, prior | {"capture_receipts": [{"document_url": "b"}]})
