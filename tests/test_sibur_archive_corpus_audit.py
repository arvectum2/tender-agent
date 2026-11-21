"""Fail-closed offline full SIBUR archive pagination and byte receipt semantics."""

from types import SimpleNamespace

import pytest

from scripts.research import audit_sibur_archive_corpus as audit


def _archive(tmp_path, monkeypatch, *, second_last=2, corrupt_page=None):
    root = tmp_path / "source-originals"
    folder = root / "categories" / "107"
    folder.mkdir(parents=True)
    for page in (1, 2):
        (folder / f"p{page:05d}.json").write_text("{}")
    monkeypatch.setattr(audit, "CATEGORIES", {"107": ("1", "Equipment")})

    def parser(directory, category, page):
        assert directory == folder and category == "107"
        if page == corrupt_page:
            raise ValueError("source hash mismatch")
        return SimpleNamespace(
            page=page, sha256=f"{page:064x}",
            last_page=2 if page == 1 else second_last,
            records=[{"external_id": f"id-{page}"}],
        )

    monkeypatch.setattr(audit, "replay_archived_page", parser)
    return root, folder


def test_complete_two_pages_checked_no_live_source_or_db(tmp_path, monkeypatch):
    root, _ = _archive(tmp_path, monkeypatch)
    result = audit.audit_corpus(root)
    assert result["status"] == "pass_historical_source_window"
    assert result["source_categories"] == 1
    assert result["verified_original_page_count"] == 2
    assert result["replayed_source_rows"] == 2
    assert result["no_network_requests"] and result["no_database_mutations"]
    assert result["current_2026_nov21_status_verified"] is False


def test_missing_or_unexpected_original_page_is_rejected(tmp_path, monkeypatch):
    root, folder = _archive(tmp_path, monkeypatch)
    (folder / "p00002.json").unlink()
    with pytest.raises(ValueError, match="incomplete or extra"):
        audit.audit_corpus(root)
    (folder / "p00002.json").write_text("{}")
    (folder / "p00003.json").write_text("{}")
    with pytest.raises(ValueError, match="incomplete or extra"):
        audit.audit_corpus(root)


def test_historical_pagination_change_never_claims_complete(tmp_path, monkeypatch):
    root, _ = _archive(tmp_path, monkeypatch, second_last=3)
    result = audit.audit_corpus(root)
    assert result["status"] == "needs_review"
    assert result["category_receipts"][0]["changed_pagination_count"] == 1
    assert result["verified_original_page_count"] == 2


def test_invalid_original_page_count_tracks_all_errors(tmp_path, monkeypatch):
    root, _ = _archive(tmp_path, monkeypatch, corrupt_page=2)
    result = audit.audit_corpus(root)
    assert result["status"] == "needs_review"
    assert result["verified_original_page_count"] == 1
    assert result["category_receipts"][0]["invalid_original_page_count"] == 1


def test_symlinked_source_root_is_rejected(tmp_path, monkeypatch):
    root, _ = _archive(tmp_path, monkeypatch)
    shortcut = tmp_path / "linked"
    shortcut.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="unsafe original archive root"):
        audit.audit_corpus(shortcut)
