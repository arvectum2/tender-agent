"""Synthetic readonly PG17 archive-integrity and 7-day claim guard."""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.ops import audit_pitr_wal_record_integrity as m

SYSTEM = "7692004809331994662"
IMAGE = "sha256:" + "a" * 64
FIRST = "000000010000000200000079"
SECOND = "00000001000000020000007A"
THIRD = "00000001000000020000007B"


def _segment(root: Path, name: str, size=m.SEGMENT_SIZE):
    with (root / name).open("wb") as output:
        output.truncate(size)


def fixture(tmp_path):
    base = tmp_path / "base-20261120T084731139954Z"
    base.mkdir()
    (base / "data").mkdir()
    receipt = base / "restore-verified.json"
    receipt.write_text(json.dumps({
        "status": "pass",
        "source_system_identifier": SYSTEM,
        "base_path": str(base / "data"),
        "manifest_verified": "backup successfully verified",
        "live_database_mutated": False,
        "image": IMAGE,
    }))
    wal = tmp_path / f"wal-{SYSTEM}"
    wal.mkdir()
    _segment(wal, FIRST)
    _segment(wal, SECOND)
    _segment(wal, THIRD + ".partial", 4128)
    return receipt, wal


def test_names_lengths_and_current_partial_not_record_proof(tmp_path):
    receipt, wal = fixture(tmp_path)
    result = m.audit(receipt, wal, SYSTEM, now=datetime(2026, 11, 22, tzinfo=UTC))
    assert result["full_segment_count"] == 2
    assert result["contiguous_names_and_exact_lengths"]
    assert result["in_progress_partial_excluded"] is True
    assert result["pg17_wal_record_decode_completed"] is False
    assert result["seven_day_base_age_condition"] is False
    assert result["seven_day_pitr_proven"] is False


def test_name_gap_rejected(tmp_path):
    receipt, wal = fixture(tmp_path)
    (wal / SECOND).rename(wal / "00000001000000020000007D")
    with pytest.raises(m.WalIntegrityError, match="wal_filename_gap"):
        m.audit(receipt, wal, SYSTEM)


def test_short_full_segment_rejected(tmp_path):
    receipt, wal = fixture(tmp_path)
    _segment(wal, SECOND, 4096)
    with pytest.raises(m.WalIntegrityError, match="invalid_full_segment_size"):
        m.audit(receipt, wal, SYSTEM)


def test_symlinked_wal_rejected(tmp_path):
    receipt, wal = fixture(tmp_path)
    (wal / SECOND).unlink()
    (wal / SECOND).symlink_to(wal / FIRST)
    with pytest.raises(m.WalIntegrityError, match="unsafe_archive_entry"):
        m.audit(receipt, wal, SYSTEM)


def test_partial_must_be_next_sequence(tmp_path):
    receipt, wal = fixture(tmp_path)
    (wal / (THIRD + ".partial")).rename(wal / (FIRST + ".partial"))
    with pytest.raises(m.WalIntegrityError, match="unrelated_partial_segment"):
        m.audit(receipt, wal, SYSTEM)


def test_backup_cluster_mismatch_fails(tmp_path):
    receipt, wal = fixture(tmp_path)
    raw = json.loads(receipt.read_text())
    raw["source_system_identifier"] = "7694400479046774822"
    receipt.write_text(json.dumps(raw))
    with pytest.raises(m.WalIntegrityError, match="backup_cluster_receipt_disagrees"):
        m.audit(receipt, wal, SYSTEM)


def test_record_verifier_is_pinned_and_does_not_claim_7days(tmp_path, monkeypatch):
    receipt, wal = fixture(tmp_path)
    calls = []
    monkeypatch.setattr(m, "verify_pg17_records", lambda *args: calls.append(args))
    future = datetime(2026, 11, 28, tzinfo=UTC)
    result = m.audit(receipt, wal, SYSTEM, verify_records=True, now=future)
    assert calls == [(wal, IMAGE, FIRST, SECOND)]
    assert result["pg17_wal_record_decode_completed"]
    assert result["seven_day_base_age_condition"] is True
    assert result["seven_day_historical_target_restored"] is False
    assert result["seven_day_pitr_proven"] is False
    assert result["production_mutations"] == 0


def test_decoder_rejects_unpinned_image(tmp_path):
    with pytest.raises(m.WalIntegrityError, match="decoder_identity_not_verified"):
        m.verify_pg17_records(tmp_path, "pgvector/pgvector:pg17", FIRST, SECOND)


def test_private_receipt_mode0600_and_never_overwrite(tmp_path):
    path = tmp_path / "output.json"
    m.write_private_once(path, {"seven_day_pitr_proven": False})
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())["seven_day_pitr_proven"] is False
    with pytest.raises(m.WalIntegrityError, match="unsafe_or_existing_private_proof"):
        m.write_private_once(path, {"seven_day_pitr_proven": True})


def test_even_seven_day_base_age_not_enough_without_restore(tmp_path):
    receipt, wal = fixture(tmp_path)
    base = datetime(2026, 11, 20, 8, 47, 31, tzinfo=UTC)
    report = m.audit(receipt, wal, SYSTEM, now=base + timedelta(days=8))
    assert report["seven_day_base_age_condition"]
    assert report["status"] == "PASS_FILENAME_SIZE_PREFLIGHT_NOT_RECORD_INTEGRITY"
    assert report["seven_day_pitr_proven"] is False
