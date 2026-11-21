"""Fail-closed provenance checks for offline first-party SIBUR registry snapshots."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from scripts.research import import_sibur_public_snapshot as importer
from scripts.research import verify_sibur_public_snapshot as verifier


def _archive(tmp_path, monkeypatch):
    root = tmp_path / "private-originals"
    root.mkdir(mode=0o700)
    original = b"original first-party SIBUR page bytes"
    digest = hashlib.sha256(original).hexdigest()
    parsed = {
        "external_id": "1234567/1", "title": "Test", "subject": "Equipment",
        "method": "Request", "published_raw": "14.11.2026", "deadline_raw": "19.11.2026 09:00",
        "organizer": "Buyer", "status_raw": "Open", "category": "Equipment",
        "documentation_label": "Doc", "source": "sibur_public",
        "source_url": "https://www.sibur.ru/ru/procurement/buy/?PAGEN_1=1",
        "source_sha256": digest, "verification": "PUBLIC_SNAPSHOT_ONLY",
        "source_row": "1", "documentation_urls": [], "unverified_document_links": 0,
    }
    legacy = {k: v for k, v in parsed.items()
              if k not in verifier.CURRENT_ONLY_FIELDS}
    manifest = {
        "source": "sibur_public", "verification": "PUBLIC_LIST_SNAPSHOT_NOT_HISTORICAL_COVERAGE",
        "page_count_stable": True, "errors": [], "announced_pages": 1,
        "validated_pages": 1, "raw_rows": 1, "unique_ids": 1,
        "pages": [{"page": 1, "last_page": 1, "bytes": len(original),
                   "sha256": digest, "rows": 1}],
    }
    (root / "page-001.json").write_bytes(original)
    (root / "receipts.json").write_text(json.dumps(manifest))
    (root / "normalized.json").write_text(json.dumps([{
        "external_id": parsed["external_id"], "observations": [legacy]
    }]))

    def fake_parse(raw, page):
        assert raw == original and page == 1
        return SimpleNamespace(sha256=digest, last_page=1, records=[parsed])

    monkeypatch.setattr(verifier, "parse_page", fake_parse)
    return root, manifest, original


def test_full_original_replay_with_historical_15_field_projection(tmp_path, monkeypatch):
    root, _, _ = _archive(tmp_path, monkeypatch)
    rows = importer.build_rows(verifier.replay_verified_originals(root))
    assert len(rows) == 1
    assert rows[0]["source"] == "sibur_public"
    assert rows[0]["application_deadline"] is None
    assert rows[0]["raw_payload"]["observations"][0]["documentation_urls"] == []
    assert rows[0]["raw_payload"]["observations"][0]["unverified_document_links"] == 0


def test_source_page_bytes_sha_mismatch_rejected(tmp_path, monkeypatch):
    root, _, raw = _archive(tmp_path, monkeypatch)
    (root / "page-001.json").write_bytes(b"x" * len(raw))
    with pytest.raises(ValueError, match="digest"):
        verifier.replay_verified_originals(root)


def test_historical_normalized_row_tamper_rejected(tmp_path, monkeypatch):
    root, _, _ = _archive(tmp_path, monkeypatch)
    path = root / "normalized.json"
    data = json.loads(path.read_text())
    data[0]["observations"][0]["title"] = "changed"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="original row content changed"):
        verifier.replay_verified_originals(root)


def test_incomplete_history_never_claims_complete(tmp_path, monkeypatch):
    root, manifest, _ = _archive(tmp_path, monkeypatch)
    manifest["announced_pages"] = 2
    (root / "receipts.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="pagination"):
        verifier.replay_verified_originals(root)


def test_source_reported_counts_not_silently_revised(tmp_path, monkeypatch):
    root, manifest, _ = _archive(tmp_path, monkeypatch)
    manifest["unique_ids"] = 2
    (root / "receipts.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="count"):
        verifier.replay_verified_originals(root)


def test_original_page_symlink_rejected(tmp_path, monkeypatch):
    root, _, _ = _archive(tmp_path, monkeypatch)
    (root / "page-001.json").unlink()
    (root / "page-001.json").symlink_to(tmp_path / "elsewhere")
    with pytest.raises(ValueError, match="linked"):
        verifier.replay_verified_originals(root)


def test_duplicate_manifest_key_rejected(tmp_path, monkeypatch):
    root, _, _ = _archive(tmp_path, monkeypatch)
    original = (root / "receipts.json").read_text()
    (root / "receipts.json").write_text(original.replace('{"source":', '{"source":"wrong","source":'))
    with pytest.raises(ValueError, match="duplicate JSON"):
        verifier.replay_verified_originals(root)


def test_public_import_main_has_no_write_or_source_call(tmp_path, monkeypatch, capsys):
    root, _, _ = _archive(tmp_path, monkeypatch)
    monkeypatch.setattr("sys.argv", ["import-sibur", "--snapshot-dir", str(root)])
    importer.main()
    result = json.loads(capsys.readouterr().out)
    assert result == {"mode": "read_only_verified_originals", "source": "sibur_public",
                      "rows": 1, "observations": 1, "database_mutated": False,
                      "originals_fetch_performed": False, "authorized_to_write": False}


def test_shape_only_hex_length_is_not_accepted():
    row = {
        "external_id": "1234567/1", "title": "Test", "subject": "Spec",
        "method": "Request", "published_raw": "14.11.2026", "deadline_raw": "19.11.2026 09:00",
        "organizer": "Buyer", "status_raw": "Open", "category": "Equipment",
        "documentation_label": "Doc", "source": "sibur_public",
        "source_url": "https://www.sibur.ru/ru/procurement/buy/?PAGEN_1=1",
        "source_sha256": "z" * 64, "verification": "PUBLIC_SNAPSHOT_ONLY",
        "source_row": "1", "documentation_urls": [], "unverified_document_links": 0,
    }
    with pytest.raises(ValueError, match="source or shape mismatch"):
        importer.build_rows([{"external_id": row["external_id"], "observations": [row]}])
