"""Offline APR06 source-byte verifier never elevates saved receipts to live EIS truth."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.acceptance.apr06_saved_bytes_audit import audit_saved_bytes

CHECKED_AT = datetime.fromisoformat("2026-10-13T13:38:00+03:00")
MANIFEST_HASH = "a" * 64


def _fixture(tmp_path: Path):
    root = tmp_path / "runs"
    run_id = "toa-run-20261009052409-9c4515"
    origin = root / run_id / "input" / "extracted"
    origin.mkdir(parents=True)
    original = origin / "original.xml"
    original.write_bytes(b"official bytes as saved, not live")
    payload = {
        "schema_version": "apr06-readonly-receipts-v1",
        "captured_at": "2026-10-09T05:28:02+00:00",
        "cases": [{
            "reg_number": "0372200172326000015",
            "run_id": run_id,
            "document_files": [{
                "file_id": "FILE-01",
                "sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
                "bytes": original.stat().st_size,
            }],
        }],
    }
    return payload, root, original


def _audit(manifest, root):
    return audit_saved_bytes(
        manifest, root, checked_at=CHECKED_AT, manifest_sha256=MANIFEST_HASH
    )


def test_exact_original_saved_bytes_success_without_source_or_human_promotion(tmp_path):
    manifest, root, _ = _fixture(tmp_path)
    result = _audit(manifest, root)
    assert result["summary"]["bytes_matched_count"] == 1
    assert result["summary"]["bytes_not_matched_count"] == 0
    assert result["cases"][0]["byte_integrity_state"] == "SAVED_BYTES_MATCH"
    assert result["cases"][0]["official_live_eis_revision_verified"] is False
    assert result["cases"][0]["complete_attachment_set_verified"] is False
    assert result["cases"][0]["human_procurement_reviewed"] is False
    assert result["human_signed_reviews"] == 0
    assert result["legal_or_commercial_acceptance"] is False


def test_changed_bytes_report_missing_not_success(tmp_path):
    manifest, root, file = _fixture(tmp_path)
    file.write_bytes(b"tampered")
    result = _audit(manifest, root)
    assert result["summary"]["bytes_not_matched_count"] == 1
    assert result["cases"][0]["byte_integrity_state"] == "SAVED_BYTES_MISSING_OR_CHANGED"


def test_file_removed_does_not_convert_to_zero_expected(tmp_path):
    manifest, root, file = _fixture(tmp_path)
    file.unlink()
    result = _audit(manifest, root)
    assert result["cases"][0]["not_matched"] == 1


def test_empty_receipt_is_explicitly_not_validated(tmp_path):
    manifest, root, _ = _fixture(tmp_path)
    manifest["cases"][0]["document_files"] = []
    result = _audit(manifest, root)
    assert result["cases"][0]["byte_integrity_state"] == "NO_SOURCE_BYTES_RECORDED"
    assert result["summary"]["cases_with_all_recorded_bytes_matched"] == 0
    assert result["summary"]["source_empty_cases"] == 1


@pytest.mark.parametrize("mutation", ["dup_reg", "dup_run", "bad_run", "bad_hash", "bad_size", "dup_file", "bad_schema"])
def test_reject_invalid_or_spoofed_manifest(tmp_path, mutation):
    manifest, root, _ = _fixture(tmp_path)
    if mutation in {"dup_reg", "dup_run"}:
        second = copy.deepcopy(manifest["cases"][0])
        if mutation == "dup_reg":
            second["run_id"] = "toa-run-20261009052410-aaaaaa"
        else:
            second["reg_number"] = "0372200172326000016"
        manifest["cases"].append(second)
    elif mutation == "bad_run":
        manifest["cases"][0]["run_id"] = "../../secret"
    elif mutation == "bad_hash":
        manifest["cases"][0]["document_files"][0]["sha256"] = "fake"
    elif mutation == "bad_size":
        manifest["cases"][0]["document_files"][0]["bytes"] = 0
    elif mutation == "dup_file":
        manifest["cases"][0]["document_files"].append(
            copy.deepcopy(manifest["cases"][0]["document_files"][0])
        )
    else:
        manifest["schema_version"] = "eis-verified"
    with pytest.raises(ValueError):
        _audit(manifest, root)


def test_symlink_file_refused(tmp_path):
    manifest, root, _ = _fixture(tmp_path)
    target = tmp_path / "external.xml"
    target.write_bytes(b"external")
    (root / manifest["cases"][0]["run_id"] / "input" / "shadow.xml").symlink_to(target)
    with pytest.raises(ValueError, match="Symlinked"):
        _audit(manifest, root)


def test_naive_timestamp_refused(tmp_path):
    manifest, root, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="timezone"):
        audit_saved_bytes(
            manifest, root, checked_at=CHECKED_AT.replace(tzinfo=None),
            manifest_sha256=MANIFEST_HASH,
        )


def test_missing_runs_root_refused(tmp_path):
    manifest, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="root"):
        _audit(manifest, tmp_path / "missing")


def test_reporting_historical_only_even_when_digest_matches(tmp_path):
    manifest, root, _ = _fixture(tmp_path)
    report = json.loads(json.dumps(_audit(manifest, root)))
    assert report["scope"] == "OFFLINE_ARCHIVED_BYTES_ONLY_NOT_LIVE_EIS_STATUS"
    assert report["network_access_required"] is False
    assert not report["cases"][0]["official_live_eis_revision_verified"]
