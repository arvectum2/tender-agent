from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from src.modules.market_intelligence.eis_coverage import audit_day, summarize_coverage


def _receipt(root: Path, *, region: str = "77", subsystem: str = "RI223",
             day: str = "2026-10-08", good: bool = True) -> Path:
    dtype = "purchaseNotice" if subsystem == "RI223" else "epNotificationEF2020"
    path = root / subsystem / dtype / day / f"region-{region}.json"
    zip_path = path.parent / f"region-{region}" / "archive-001" / "documentation-archive.zip"
    zip_path.parent.mkdir(parents=True)
    zip_path.write_bytes(b"PK_FAKE_TEST_ARCHIVE")
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    value = {
        "subsystem": subsystem, "document_type": dtype, "exact_date": day,
        "region": region, "status": "complete_with_archive_scan",
        "archive_scan_complete": True, "archive_count": 1,
        "archives": [{
            "index": 1, "archive_sha256": digest,
            "xml_documents_inspected": 2,
        }],
    }
    if not good:
        value["archive_scan_complete"] = False
        value["status"] = "complete"
    path.write_text(json.dumps(value))
    return zip_path


def test_sparse_days_cannot_be_called_market_coverage(tmp_path: Path):
    _receipt(tmp_path)
    result = summarize_coverage(
        root=tmp_path, first=date(2026, 10, 8), last=date(2026, 10, 9),
        regions=["77"], subsystems=["RI223", "PRIZ"],
    )
    assert result["total_source_day_slots"] == 4
    assert result["verified_day_slots"] == 1
    assert result["missing_day_slots"] == 3
    assert result["sha_verified_archives"] == 1
    assert result["xml_documents_inspected_not_unique_tenders"] == 2
    assert result["historical_exhaustiveness_verified"] is False
    assert result["winner_contracts_verified"] is False


def test_receipt_tamper_invalidates_day_and_wipes_count(tmp_path: Path):
    zip_path = _receipt(tmp_path)
    zip_path.write_bytes(b"MODIFIED_NOT_ORIGINAL")
    cell = audit_day(tmp_path, "77", date(2026, 10, 8), "RI223")
    assert cell["status"] == "evidence_invalid"
    assert cell["sha_verified_archives"] == 0
    assert cell["xml_documents_inspected"] == 0


def test_incomplete_archive_scan_not_counted(tmp_path: Path):
    _receipt(tmp_path, good=False)
    result = summarize_coverage(
        root=tmp_path, first=date(2026, 10, 8), last=date(2026, 10, 8),
        regions=["77"], subsystems=["RI223"],
    )
    assert result["incomplete_day_slots"] == 1
    assert result["verified_day_slots"] == 0


def test_receipt_region_mismatch_not_cross_tenant_or_cross_region(tmp_path: Path):
    _receipt(tmp_path, region="78")
    path = tmp_path / "RI223/purchaseNotice/2026-10-08/region-78.json"
    receipt = json.loads(path.read_text())
    receipt["region"] = "77"
    path.write_text(json.dumps(receipt))
    assert audit_day(tmp_path, "78", date(2026, 10, 8), "RI223")["status"] == "evidence_invalid"


def test_symlinked_archive_fails_closed(tmp_path: Path):
    saved = _receipt(tmp_path)
    backup = tmp_path / "outside"
    saved.rename(backup)
    try:
        saved.symlink_to(backup)
    except (NotImplementedError, OSError):
        pytest.skip("Symlinks unavailable")
    assert audit_day(tmp_path, "77", date(2026, 10, 8), "RI223")["status"] == "evidence_invalid"


def test_months_are_scoped_to_requested_interval_not_pseudo_zeroes(tmp_path: Path):
    _receipt(tmp_path, day="2026-09-30")
    _receipt(tmp_path, day="2026-10-01")
    result = summarize_coverage(
        root=tmp_path, first=date(2026, 9, 30), last=date(2026, 10, 1),
        regions=["77"], subsystems=["RI223"],
    )
    assert [r["month"] for r in result["monthly"]] == ["2026-09", "2026-10"]
    assert all(r["requested_days"] == 1 for r in result["monthly"])
    assert all(r["verified_days"] == 1 for r in result["monthly"])


@pytest.mark.parametrize(("first", "last", "regions"), [
    (date(2026, 10, 9), date(2026, 10, 8), ["77"]),
    (date(2022, 1, 1), date(2026, 10, 8), ["77"]),
    (date(2026, 10, 8), date(2026, 10, 8), ["bad"]),
    (date(2026, 10, 8), date(2026, 10, 8), ["77", "77"]),
])
def test_rejects_unbounded_or_ambiguous_horizon(tmp_path, first, last, regions):
    with pytest.raises(ValueError):
        summarize_coverage(
            root=tmp_path, first=first, last=last,
            regions=regions, subsystems=["RI223"],
        )
