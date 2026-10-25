"""Independent integrity and non-exhaustiveness validation for EIS source audits."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.eis_receipt_audit import audit_receipts


@pytest.fixture
def sample_root(tmp_path: Path) -> Path:
    d = tmp_path / "RI223/purchaseNotice/2026-10-08"
    a = d / "region-77" / "archive-001"
    a.mkdir(parents=True)
    archive = a / "documentation-archive.zip"
    archive.write_bytes(b"PK_test-fixture-no-real-procurement")
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    receipt = {
        "schema_version": "mi-eis-soap-receipt/0.1",
        "subsystem": "RI223", "document_type": "purchaseNotice",
        "region": "77", "exact_date": "2026-10-08",
        "attempt_utc": "2026-10-25T05:00:00+00:00",
        "status": "complete_with_archive_scan",
        "archive_scan_complete": True, "archive_count": 1,
        "archives": [{
            "index": 1, "archive_sha256": sha, "xml_documents_inspected": 3,
            "matches": [{"family": "statcom"}],
        }],
    }
    (d / "region-77.json").write_text(json.dumps(receipt), encoding="utf-8")
    return tmp_path


def test_audit_counts_verified_samples_and_never_claims_national_coverage(sample_root):
    report = audit_receipts(sample_root, attempt_date="2026-10-25")
    assert report["sampled_source_region_days"] == 1
    assert report["verified_zip_archives"] == 1
    assert report["xml_documents_scanned"] == 3
    assert report["lexical_candidate_occurrences"] == 1
    assert report["national_or_monthly_coverage_established"] is False
    assert report["unique_procurements_established"] is False
    assert report["rows"][0]["region"] == "77"


def test_audit_rejects_archive_tampering(sample_root):
    path = sample_root / "RI223/purchaseNotice/2026-10-08/region-77/archive-001/documentation-archive.zip"
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        audit_receipts(sample_root, attempt_date="2026-10-25")


def test_audit_rejects_inconsistent_counts_and_bad_date(sample_root):
    p = sample_root / "RI223/purchaseNotice/2026-10-08/region-77.json"
    source = json.loads(p.read_text())
    source["archive_count"] = 2
    p.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="inconsistent"):
        audit_receipts(sample_root, attempt_date="2026-10-25")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        audit_receipts(sample_root, attempt_date="today")


def test_audit_does_not_mistake_unchecked_failure_for_zero_demand(sample_root):
    p = sample_root / "RI223/purchaseNotice/2026-10-08/region-77.json"
    source = json.loads(p.read_text())
    source.update(status="retryable_network_failure", archive_scan_complete=False,
                  archive_count=None, archives=None)
    p.write_text(json.dumps(source))
    report = audit_receipts(sample_root, attempt_date="2026-10-25")
    assert report["verified_source_region_days"] == 0
    assert report["rows"][0]["xml_documents_scanned"] is None
    assert report["rows"][0]["lexical_candidate_occurrences"] is None


def test_two_regions_require_region_scoped_archives(sample_root):
    d = sample_root / "RI223/purchaseNotice/2026-10-08"
    expected = d / "region-77/archive-001/documentation-archive.zip"
    row_78 = json.loads((d / "region-77.json").read_text())
    row_78["region"] = "78"
    (d / "region-78.json").write_text(json.dumps(row_78))
    with pytest.raises(ValueError, match="ZIP missing"):
        audit_receipts(sample_root, attempt_date="2026-10-25")
    target = d / "region-78/archive-001/documentation-archive.zip"
    target.parent.mkdir(parents=True)
    target.write_bytes(expected.read_bytes())
    r = audit_receipts(sample_root, attempt_date="2026-10-25")
    assert r["verified_source_region_days"] == 2
    assert r["verified_zip_archives"] == 2


def test_audit_refuses_legacy_collision_marker(sample_root):
    (sample_root / "UNTRUSTED_REGION_COLLISION.json").write_text('{"invalid":true}')
    with pytest.raises(ValueError, match="unsafe legacy"):
        audit_receipts(sample_root, attempt_date="2026-10-25")
