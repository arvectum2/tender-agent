"""Synthetic fail-closed tests; never access a real SIBUR source or private files."""
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts.research import audit_sibur_ppt_saved_format as mod

URL = "https://www.sibur.ru/upload/tmp/example/synthetic.ppt"
REFERENCES = [{
    "external_id": "1234567/1",
    "source_sha256": "a" * 64,
    "source_row": "1",
    "source_url": "https://www.sibur.ru/ru/procurement/buy/?PAGEN_1=1",
}]


def fixture_files(tmp_path: Path, monkeypatch, presentation_type=None):
    snapshot = tmp_path / "source"
    saved = tmp_path / "saved"
    snapshot.mkdir()
    saved.mkdir()
    monkeypatch.setattr(mod, "source_refs", lambda path: {URL: REFERENCES})
    main_type = presentation_type or mod.SLIDESHOW_TYPE
    original = saved / "temporary.zip"
    with zipfile.ZipFile(original, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Override PartName="/ppt/presentation.xml" ContentType="'
            + main_type + '"/></Types>',
        )
        archive.writestr("ppt/presentation.xml", "<p:presentation/>")
        archive.writestr("ppt/slides/slide1.xml", "<p:sld/>")
    content = original.read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    data_path = saved / (sha + ".pptx")
    original.rename(data_path)
    receipt = {
        "url": URL,
        "status": "captured",
        "source_extension": ".ppt",
        "observed_format": "pptx",
        "mime": "application/vnd.ms-powerpoint",
        "sha256": sha,
        "bytes": len(content),
        "file": data_path.name,
        "references": REFERENCES,
    }
    receipt_path = saved / (hashlib.sha256(URL.encode()).hexdigest() + ".json")
    receipt_path.write_text(json.dumps(receipt))
    return snapshot, saved, data_path, receipt_path, receipt


def test_historical_ooxml_slideshow_is_not_original_legacy_ppt(tmp_path, monkeypatch):
    snapshot, saved, path, _, _ = fixture_files(tmp_path, monkeypatch)
    result = mod.audit(snapshot, saved)
    assert result["status"] == "needs_review"
    assert result["suspect_count"] == 1
    assert result["source_binary_original_ppt_verified"] is False
    assert result["source_latest_revision_verified"] is False
    assert result["safe_original_promotion"] is False
    assert result["external_source_requests"] == result["database_mutations"] == 0
    assert result["suspect"]["ooxml_slideshow_main_part"] is True
    assert result["suspect"]["legacy_ppt_original"] is False
    assert result["suspect"]["slides"] == 1
    assert result["suspect"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_original_receipt_must_match_source_links(tmp_path, monkeypatch):
    snapshot, saved, _, receipt_path, receipt = fixture_files(tmp_path, monkeypatch)
    receipt["references"] = []
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(mod.SourceFormatError, match="original_reference_or_receipt_mismatch"):
        mod.audit(snapshot, saved)


def test_saved_binary_tamper_is_rejected(tmp_path, monkeypatch):
    snapshot, saved, path, _, _ = fixture_files(tmp_path, monkeypatch)
    path.write_bytes(path.read_bytes() + b"extra")
    with pytest.raises(mod.SourceFormatError, match="saved_binary_identity_invalid"):
        mod.audit(snapshot, saved)


def test_non_slideshow_main_part_cannot_pass(tmp_path, monkeypatch):
    snapshot, saved, _, _, _ = fixture_files(
        tmp_path, monkeypatch,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
    )
    with pytest.raises(mod.SourceFormatError, match="slideshow_main_part_unverified"):
        mod.audit(snapshot, saved)


def test_duplicate_receipt_member_fails_closed(tmp_path, monkeypatch):
    snapshot, saved, _, receipt_path, _ = fixture_files(tmp_path, monkeypatch)
    raw = receipt_path.read_text()
    receipt_path.write_text(raw.replace('"status": "captured"', '"status": "captured", "status": "captured"'))
    with pytest.raises(mod.SourceFormatError, match="duplicate_json_member"):
        mod.audit(snapshot, saved)


def test_linked_binary_is_never_accepted(tmp_path, monkeypatch):
    snapshot, saved, path, _, _ = fixture_files(tmp_path, monkeypatch)
    other = saved / "another.pptx"
    path.rename(other)
    path.symlink_to(other)
    with pytest.raises(mod.SourceFormatError, match="saved_binary_identity_invalid"):
        mod.audit(snapshot, saved)


def test_private_receipt_create_once_and_mode0600(tmp_path):
    proof = tmp_path / "private.json"
    mod.save_private_once(proof, {"status": "needs_review", "source_binary_original_ppt_verified": False})
    assert proof.stat().st_mode & 0o777 == 0o600
    assert json.loads(proof.read_text())["status"] == "needs_review"
    with pytest.raises(mod.SourceFormatError, match="unsafe_or_existing_private_proof_path"):
        mod.save_private_once(proof, {"status": "approved"})


def test_unknown_source_host_not_treated_first_party(tmp_path, monkeypatch):
    snapshot, saved, _, _, _ = fixture_files(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "source_refs", lambda path: {
        URL.replace("www.sibur.ru", "untrusted.example"): REFERENCES,
    })
    with pytest.raises(mod.SourceFormatError, match="source_url_outside_first_party"):
        mod.audit(snapshot, saved)
