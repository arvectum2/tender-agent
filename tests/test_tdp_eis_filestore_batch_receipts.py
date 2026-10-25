"""Offline strict EIS original-retrieval receipt reconciliation tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "acceptance"))
from verify_eis_filestore_receipts import verify_full_recheck


def _inputs() -> tuple[dict, dict]:
    originals = []
    results = []
    for i in range(2):
        uid = f"{i + 1:032X}"
        original = {"official_file_uid": uid, "stored_sha256": "a" * 64,
                    "stored_bytes": 24 + i, "uid_in_official_archive_xml": True,
                    "reg_number": "0372200172326000015"}
        result = {"uid": uid, "reg_number": original["reg_number"],
                  "result": "verified", "sha256_equal": True, "size_equal": True,
                  "source_binary_verified": True, "actual_bytes": 24 + i}
        originals.append(original)
        results.append(result)
    return {"files": originals}, {"results": results}


def test_all_distinct_official_binary_receipts_reconciled() -> None:
    source, proof = _inputs()
    assert verify_full_recheck(source, proof, required=2)["verified_bytes"] == 49
    assert not verify_full_recheck(source, proof, required=2)["live_dp_original_identity_verified"]


@pytest.mark.parametrize("field,value", [
    ("result", "unavailable"), ("sha256_equal", False),
    ("size_equal", False), ("source_binary_verified", False),
    ("actual_bytes", 100), ("reg_number", "1111111111111111111"),
])
def test_false_or_incomplete_proof_rejected(field: str, value: object) -> None:
    source, proof = _inputs()
    proof["results"][1][field] = value
    with pytest.raises(ValueError, match="unverified"):
        verify_full_recheck(source, proof, required=2)


def test_duplicate_or_missing_official_file_rejected() -> None:
    source, proof = _inputs()
    source["files"][1]["official_file_uid"] = source["files"][0]["official_file_uid"]
    with pytest.raises(ValueError):
        verify_full_recheck(source, proof, required=2)
    source, proof = _inputs()
    proof["results"].pop()
    with pytest.raises(ValueError):
        verify_full_recheck(source, proof, required=2)


def test_uid_must_be_anchored_to_official_xml() -> None:
    source, proof = _inputs()
    source["files"][0]["uid_in_official_archive_xml"] = False
    with pytest.raises(ValueError, match="official_source"):
        verify_full_recheck(source, proof, required=2)
