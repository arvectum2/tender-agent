"""Fail-closed source identity and historical DP provenance without external access."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.research import verify_sibur_dp_source_provenance as proof
from src.modules.tender_connectors.sibur.archive_parser import archive_url


def _fixture(tmp_path, monkeypatch):
    documents = tmp_path / "documents"
    documents.mkdir()
    archive = tmp_path / "archive"
    archive_documents = archive / "categories" / "documents"
    archive_documents.mkdir(parents=True)
    registry = tmp_path / "registry"
    registry.mkdir()
    current_url = "https://www.sibur.ru/upload/tmp/example/first.xlsx"
    archived_url = "https://www.sibur.ru/upload/tmp/example/second.xlsx"
    first = b"first original xlsx bytes"
    second = b"second original xlsx bytes"
    sha_first = hashlib.sha256(first).hexdigest()
    sha_second = hashlib.sha256(second).hexdigest()
    (documents / (sha_first + ".xlsx")).write_bytes(first)
    (documents / (sha_second + ".xlsx")).write_bytes(second)
    (archive_documents / (sha_second + ".xlsx")).write_bytes(second)
    registry_row = {
        "source_sha256": "f" * 64, "source_row": "1", "external_id": "1111111/1",
        "source_url": "https://www.sibur.ru/ru/procurement/buy/?PAGEN_1=1",
    }
    archived_row = {
        "source_sha256": "a" * 64, "source_row": "2", "external_id": "2222222/1",
        "source_url": archive_url("107", 1),
    }
    def receipt(directory, url, sha, raw, refs):
        path = directory / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        value = {
            "url": url, "sha256": sha, "status": "captured",
            "file": sha + ".xlsx", "bytes": len(raw), "references": refs,
        }
        path.write_text(json.dumps(value))
        return path
    current_path = receipt(documents, current_url, sha_first, first, [registry_row])
    archive_path = receipt(archive_documents, archived_url, sha_second, second, [archived_row])
    monkeypatch.setattr(proof, "load", lambda _: {
        sha_first: {"chunks": 2}, sha_second: {"chunks": 3},
    })
    monkeypatch.setattr(proof, "source_refs", lambda _: {current_url: [registry_row]})

    def replay(_directory, category, page):
        assert category == "107" and page == 1
        return SimpleNamespace(sha256="a" * 64, records=[{
            "source_url": archived_row["source_url"],
            "source_row": "2", "external_id": "2222222/1",
            "documentation_urls": [archived_url],
        }])

    monkeypatch.setattr(proof, "replay_archived_page", replay)
    return (registry, documents, archive, current_path, archive_path,
            sha_first, sha_second)


def test_two_independent_first_party_source_origins_complete(tmp_path, monkeypatch):
    snapshot, docs, archive, *_ = _fixture(tmp_path, monkeypatch)
    result = proof.verify_saved_source_lineage(snapshot, docs, archive)
    assert result["status"] == "historical_first_party_source_lineage_verified"
    assert result["original_sha256_count"] == 2
    assert result["primary_registry_source_count"] == 1
    assert result["historical_archive_category_source_count"] == 1
    assert result["historical_DP_matching_chunk_embeddings"] == 5
    assert result["network_requests"] == result["db_mutations"] == 0
    assert result["live_source_current_status_verified"] is False


def test_missing_second_source_url_never_promotes_DP_bytes(tmp_path, monkeypatch):
    snapshot, docs, archive, _, path, *_ = _fixture(tmp_path, monkeypatch)
    path.unlink()
    with pytest.raises(ValueError, match="provenance incomplete"):
        proof.verify_saved_source_lineage(snapshot, docs, archive)


def test_archive_receipt_source_row_must_match_sha_pinned_page(tmp_path, monkeypatch):
    snapshot, docs, archive, _, path, *_ = _fixture(tmp_path, monkeypatch)
    value = json.loads(path.read_text())
    value["references"][0]["external_id"] = "invented-procurement-id"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="row-to-document linkage"):
        proof.verify_saved_source_lineage(snapshot, docs, archive)


def test_changed_archive_original_bytes_rejected(tmp_path, monkeypatch):
    snapshot, docs, archive, _, _, _, sha = _fixture(tmp_path, monkeypatch)
    (archive / "categories" / "documents" / (sha + ".xlsx")).write_bytes(b"different")
    with pytest.raises(ValueError, match="SHA mismatch"):
        proof.verify_saved_source_lineage(snapshot, docs, archive)


def test_wrong_historical_page_digest_rejected(tmp_path, monkeypatch):
    snapshot, docs, archive, _, path, *_ = _fixture(tmp_path, monkeypatch)
    value = json.loads(path.read_text())
    value["references"][0]["source_sha256"] = "b" * 64
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="original page digest"):
        proof.verify_saved_source_lineage(snapshot, docs, archive)


def test_archive_receipt_external_origin_rejected(tmp_path, monkeypatch):
    snapshot, docs, archive, _, path, *_ = _fixture(tmp_path, monkeypatch)
    value = json.loads(path.read_text())
    value["url"] = "https://evil.example/second.xlsx"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="identity not derived"):
        proof.verify_saved_source_lineage(snapshot, docs, archive)


def test_duplicate_receipt_field_rejected(tmp_path, monkeypatch):
    snapshot, docs, archive, _, path, *_ = _fixture(tmp_path, monkeypatch)
    path.write_text(path.read_text().replace('{"url":', '{"url":"forged","url":'))
    with pytest.raises(ValueError, match="duplicate original-document receipt"):
        proof.verify_saved_source_lineage(snapshot, docs, archive)


def test_symlink_archive_document_body_refused(tmp_path, monkeypatch):
    snapshot, docs, archive, _, _, _, sha = _fixture(tmp_path, monkeypatch)
    body = archive / "categories" / "documents" / (sha + ".xlsx")
    body.unlink()
    body.symlink_to(Path(tmp_path) / "unverified")
    with pytest.raises(ValueError, match="unsafe or oversized"):
        proof.verify_saved_source_lineage(snapshot, docs, archive)


def test_default_cli_reports_historical_only(tmp_path, monkeypatch, capsys):
    snapshot, docs, archive, *_ = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr("sys.argv", [
        "verify-source", "--registry-snapshot", str(snapshot),
        "--documents", str(docs), "--archive-root", str(archive),
    ])
    proof.main()
    result = json.loads(capsys.readouterr().out)
    assert result["original_sha256_count"] == 2
    assert result["new_source_admission_authorized"] is False
    assert result["live_DP_state_verified"] is False
    assert result["network_requests"] == result["db_mutations"] == 0
