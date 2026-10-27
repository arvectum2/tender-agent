import hashlib
import json
from pathlib import Path

from src.modules.market_intelligence.pq_public_223_direct import merge_direct


def test_sha_direct_attachment_is_deduped_and_keeps_public_source_tier(tmp_path: Path):
    root = tmp_path / "source"
    folder = root / "32616280467"
    folder.mkdir(parents=True)
    raw = b"%PDF-1.6\noriginal commission protocol"
    sha = hashlib.sha256(raw).hexdigest()
    (folder / "minutes.pdf").write_bytes(raw)
    (folder / "public-page-receipt.json").write_text(json.dumps({
        "schema_version": "pq-223-public-page-download/1",
        "registry_number": folder.name, "public_page_sha256": "1" * 64,
        "files": [{"filename": "minutes.pdf", "sha256": sha}]}))
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "canonical-manifest.json").write_text(json.dumps({
        "schema_version": "pq-public-canonical/1", "records": []}))
    result = merge_direct(source_root=root, canonical=canonical)
    assert result["direct_files_added"] == 1
    manifest = json.loads((canonical / "canonical-manifest.json").read_text())
    assert manifest["records"][0]["original_xml_binding_verified"] is False
    assert manifest["records"][0]["source_kind"] == "public_eis_direct_attachment"
    assert (canonical / folder.name / (sha + ".pdf")).read_bytes() == raw
    assert merge_direct(source_root=root, canonical=canonical)["direct_files_added"] == 0


def test_source_digest_mismatch_cannot_enter_canonical_corpus(tmp_path: Path):
    root = tmp_path / "source"
    folder = root / "32616280467"
    folder.mkdir(parents=True)
    (folder / "minutes.pdf").write_bytes(b"tampered")
    (folder / "public-page-receipt.json").write_text(json.dumps({
        "schema_version": "pq-223-public-page-download/1",
        "registry_number": folder.name,
        "files": [{"filename": "minutes.pdf", "sha256": "f" * 64}]}))
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "canonical-manifest.json").write_text(json.dumps({
        "schema_version": "pq-public-canonical/1", "records": []}))
    result = merge_direct(source_root=root, canonical=canonical)
    assert result["direct_files_added"] == 0
    assert result["errors"][0]["status"] == "source_sha_mismatch"
