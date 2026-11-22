"""Synthetic first-party historical import manifest pairing, offline-only."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.audit_sibur_import_window import (
    ImportWindowError,
    audit_import_window,
)


def fixture_batches(tmp_path: Path, *, count=2):
    rows = []
    for i in range(count):
        source = {
            "schema": "sibur_archive_pages_v1",
            "groups": [{"external_id": f"{1000000 + i}/1", "observations": []}],
            "pages": [{"category": "107", "page": i + 1}],
            "review": [],
            "older_rows": i,
        }
        raw = json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
        sha = hashlib.sha256(raw).hexdigest()
        inp = tmp_path / (sha + ".input.json")
        inp.write_bytes(raw)
        result = {
            "source_input_sha256": sha,
            "result": {"inserted": 1, "older_rows_retained_privately": i},
            "replay": {"exact_replay": 1},
            "backup": {"saved": True},
        }
        out = tmp_path / (hashlib.sha256(str(i).encode()).hexdigest() + ".result.json")
        out.write_text(json.dumps(result))
        rows.append((inp, out, source, result))
    return rows


def test_readonly_pairing_counts_and_category_exclusion(tmp_path):
    fixture_batches(tmp_path)
    result = audit_import_window(tmp_path, expected_batches=2)
    assert result["status"] == "PASS_HISTORICAL_IMPORT_SELECTION_ONLY"
    assert result["batches_input_result"] == 2
    assert result["unique_selected_group_ids"] == 2
    assert result["pre2024_source_observations_retained_privately"] == 1
    assert result["excluded_support_category"] == "999_19"
    assert result["external_source_requests"] == result["database_mutations"] == 0


def test_no_missing_or_extra_result_receipts(tmp_path):
    rows = fixture_batches(tmp_path)
    rows[1][1].unlink()
    with pytest.raises(ImportWindowError, match="membership_changed"):
        audit_import_window(tmp_path, expected_batches=2)


def test_modified_input_byte_rejected(tmp_path):
    rows = fixture_batches(tmp_path)
    path = rows[0][0]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ImportWindowError, match="input_hash_or_schema"):
        audit_import_window(tmp_path, expected_batches=2)


def test_result_must_link_exact_original_input(tmp_path):
    rows = fixture_batches(tmp_path)
    path = rows[0][1]
    result = rows[0][3]
    result["source_input_sha256"] = "f" * 64
    path.write_text(json.dumps(result))
    with pytest.raises(ImportWindowError, match="not_linked"):
        audit_import_window(tmp_path, expected_batches=2)


def test_older_rows_cannot_drift_from_receipt(tmp_path):
    rows = fixture_batches(tmp_path)
    path = rows[0][1]
    result = rows[0][3]
    result["result"]["older_rows_retained_privately"] = 100
    path.write_text(json.dumps(result))
    with pytest.raises(ImportWindowError, match="retention_inconsistent|excluded_import_result"):
        audit_import_window(tmp_path, expected_batches=2)


def test_support_services_not_silently_in_original_eight_batches(tmp_path):
    rows = fixture_batches(tmp_path)
    source = rows[0][2]
    source["pages"][0]["category"] = "999_19"
    raw = json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
    old_input = rows[0][0]
    old_input.unlink()
    new_input = tmp_path / (hashlib.sha256(raw).hexdigest() + ".input.json")
    new_input.write_bytes(raw)
    result = rows[0][3]
    result["source_input_sha256"] = new_input.name[:64]
    rows[0][1].write_text(json.dumps(result))
    with pytest.raises(ImportWindowError, match="unexpected_historical_import_category"):
        audit_import_window(tmp_path, expected_batches=2)


def test_duplicate_input_json_member_rejected(tmp_path):
    rows = fixture_batches(tmp_path)
    raw = rows[0][0].read_bytes().replace(b'"schema":', b'"schema":"duplicate", "schema":', 1)
    old = rows[0][0]
    old.unlink()
    new = tmp_path / (hashlib.sha256(raw).hexdigest() + ".input.json")
    new.write_bytes(raw)
    result = rows[0][3]
    result["source_input_sha256"] = new.name[:64]
    rows[0][1].write_text(json.dumps(result))
    with pytest.raises(ImportWindowError, match="duplicate_json_key"):
        audit_import_window(tmp_path, expected_batches=2)


def test_symlink_source_input_cannot_be_used(tmp_path):
    rows = fixture_batches(tmp_path)
    path = rows[0][0]
    original = tmp_path / "original.bin"
    path.rename(original)
    path.symlink_to(original)
    with pytest.raises(ImportWindowError, match="untrusted_manifest"):
        audit_import_window(tmp_path, expected_batches=2)
