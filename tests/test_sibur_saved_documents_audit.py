"""Historical SIBUR attachment receipts must never be mistaken for live permission."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.research import acquire_sibur_documents as acquisition
from scripts.research import audit_sibur_saved_documents as audit

SOURCE_URL = "https://www.sibur.ru/upload/tmp/example/report.pdf"
REFERENCES = [{
    "external_id": "1234567/1", "source_row": "1", "source_sha256": "a" * 64,
    "source_url": "https://www.sibur.ru/ru/procurement/buy/?PAGEN_1=1",
}]


def _saved(tmp_path, monkeypatch, *, url=SOURCE_URL, saved_ext=None):
    directory = tmp_path / "existing-evidence"
    directory.mkdir()
    original_ext = Path(url).suffix.lower()
    ext = saved_ext or original_ext
    content = b"%PDF-1.7\noriginal" if ext == ".pdf" else b"PK\x03\x04metadata"
    sha = hashlib.sha256(content).hexdigest()
    (directory / (sha + ext)).write_bytes(content)
    receipt = {
        "url": url, "references": REFERENCES, "status": "captured",
        "sha256": sha, "file": sha + ext, "bytes": len(content),
        "mime": "application/octet-stream", "observed_at": "2026-11-14T19:00:00+00:00",
    }
    receipt_path = directory / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    receipt_path.write_text(json.dumps(receipt))
    monkeypatch.setattr(audit, "source_refs", lambda _: {url: REFERENCES})
    return directory, receipt_path, sha


def test_exact_first_party_saved_pdf_audit_has_no_source_or_db_calls(tmp_path, monkeypatch):
    directory, _, _ = _saved(tmp_path, monkeypatch)
    result = audit.audit_saved_documents(tmp_path, directory)
    assert result["status"] == "verified_historical_offline"
    assert result["source_filename_aligned_sha_verified"] == 1
    assert result["supported_signature_checked"] == 1
    assert result["source_url_extension_mismatch_quarantined"] == 0
    assert result["db_mutations"] == result["network_requests"] == 0
    assert result["legal_status_current_verified"] is False


def test_historical_ppt_url_with_pptx_file_quarantined(tmp_path, monkeypatch):
    url = SOURCE_URL.replace("report.pdf", "slides.ppt")
    directory, _, _ = _saved(tmp_path, monkeypatch, url=url, saved_ext=".pptx")
    result = audit.audit_saved_documents(tmp_path, directory)
    assert result["status"] == "needs_review"
    assert result["all_first_party_original_filenames_verified"] is False
    assert result["source_url_extension_mismatch_quarantined"] == 1
    assert result["source_filename_aligned_sha_verified"] == 0


def test_wrong_content_hash_rejected(tmp_path, monkeypatch):
    directory, _, sha = _saved(tmp_path, monkeypatch)
    (directory / (sha + ".pdf")).write_bytes(b"%PDF-1.7\nDIFFERENT!")
    with pytest.raises(ValueError, match="size mismatch|differ from receipt SHA"):
        audit.audit_saved_documents(tmp_path, directory)


def test_tampered_linked_observation_rejected(tmp_path, monkeypatch):
    directory, path, _ = _saved(tmp_path, monkeypatch)
    receipt = json.loads(path.read_text())
    receipt["references"][0]["external_id"] = "wrong-source-identity"
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="first-party original source member"):
        audit.audit_saved_documents(tmp_path, directory)


def test_unexpected_saved_receipt_rejected(tmp_path, monkeypatch):
    directory, _, _ = _saved(tmp_path, monkeypatch)
    (directory / ("b" * 64 + ".json")).write_text("{}")
    with pytest.raises(ValueError, match="URL receipt membership"):
        audit.audit_saved_documents(tmp_path, directory)


def test_unsafe_document_symlink_rejected(tmp_path, monkeypatch):
    directory, _, sha = _saved(tmp_path, monkeypatch)
    file = directory / (sha + ".pdf")
    file.unlink()
    file.symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="body missing"):
        audit.audit_saved_documents(tmp_path, directory)


def test_nonstandard_saved_name_rejected(tmp_path, monkeypatch):
    directory, path, _ = _saved(tmp_path, monkeypatch)
    receipt = json.loads(path.read_text())
    receipt["file"] = "../unsafe-file.pdf"
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="filename is not consistent"):
        audit.audit_saved_documents(tmp_path, directory)


def test_no_network_default_cli_and_review_is_nonzero(tmp_path, monkeypatch, capsys):
    directory, _, _ = _saved(tmp_path, monkeypatch)
    monkeypatch.setattr(audit, "audit_saved_documents", lambda *args: {
        "status": "needs_review", "network_requests": 0, "db_mutations": 0,
    })
    monkeypatch.setattr(acquisition, "fetch", lambda *args: pytest.fail("unexpected fetch"))
    monkeypatch.setattr("sys.argv", [
        "acquire-sibur", "--snapshot", str(tmp_path), "--output", str(directory),
    ])
    with pytest.raises(SystemExit, match="2"):
        acquisition.main()
    assert json.loads(capsys.readouterr().out)["status"] == "needs_review"


def test_duplicate_receipt_fields_rejected(tmp_path, monkeypatch):
    directory, path, _ = _saved(tmp_path, monkeypatch)
    raw = path.read_text()
    path.write_text(raw.replace('{"url":', '{"url":"wrong","url":'))
    with pytest.raises(ValueError, match="duplicate document receipt field"):
        audit.audit_saved_documents(tmp_path, directory)
