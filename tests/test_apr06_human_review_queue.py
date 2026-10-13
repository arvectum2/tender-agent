"""APR-06 machine receipts are not independent human acceptance."""

from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.acceptance.build_apr06_human_review_queue import (
    COLUMNS,
    build_queue,
)


def _sources():
    receipt = {
        "reg_number": "0158300034526000388",
        "run_id": "toa-run-synthetic",
        "status": "needs_review",
        "archive_download_status": "downloaded",
        "notice_sha256": "a" * 64,
        "operator_reviewed": False,
        "official_notice_revision_verified_by_human": False,
        "document_files": [
            {"file_id": "FILE-01", "sha256": "b" * 64, "bytes": 128},
            {"file_id": "FILE-02", "sha256": "c" * 64, "bytes": 235},
        ],
    }
    return {"cases": [receipt]}, {
        "critical_mismatches": [
            {"reg_number": "0158300034526000388", "type": "STALE_DEADLINE"}
        ],
        "human_operator_review": False,
    }


def test_queue_has_source_counts_and_all_human_decisions_empty():
    receipts, audit = _sources()
    row, = build_queue(receipts, audit)
    assert tuple(row) == COLUMNS
    assert row["reg_number"] == "0158300034526000388"
    assert row["file_count"] == 2
    assert row["hashed_file_count"] == 2
    assert row["machine_revision_mismatch_flag"] == "MACHINE_REVIEW_FLAG"
    assert row["source_receipt_operator_reviewed"] == "false"
    assert row["source_receipt_revision_human_verified"] == "false"
    for field in (
        "current_official_notice_revision",
        "original_binary_eis_verified",
        "document_completeness_human_checked",
        "source_fact_citations_human_checked",
        "human_go_no_go_defer",
        "human_reviewer",
        "human_review_timestamp",
        "human_signoff_reference",
    ):
        assert row[field] == ""


def test_model_audit_verdict_cannot_fill_human_verdict():
    receipts, audit = _sources()
    audit["cases"] = [{"machine_decision": "GO", "human_confirmed": True}]
    row, = build_queue(receipts, audit)
    assert row["human_go_no_go_defer"] == ""
    assert row["human_signoff_reference"] == ""


@pytest.mark.parametrize("bad", ["not-a-number", "99999", "012345678901234567890"])
def test_malformed_registry_fails_closed(bad):
    receipts, audit = _sources()
    receipts["cases"][0]["reg_number"] = bad
    audit["critical_mismatches"] = []
    with pytest.raises(ValueError):
        build_queue(receipts, audit)


def test_duplicate_registry_fails_closed():
    receipts, audit = _sources()
    receipts["cases"].append(deepcopy(receipts["cases"][0]))
    with pytest.raises(ValueError, match="duplicated"):
        build_queue(receipts, audit)


@pytest.mark.parametrize("field", ["operator_reviewed", "official_notice_revision_verified_by_human"])
def test_machine_receipt_must_not_be_trusted_as_human_signature(field):
    receipts, audit = _sources()
    receipts["cases"][0][field] = True
    with pytest.raises(ValueError, match="human review"):
        build_queue(receipts, audit)


def test_malformed_document_digest_fails_closed():
    receipts, audit = _sources()
    receipts["cases"][0]["document_files"][1]["sha256"] = "wrong"
    with pytest.raises(ValueError, match="SHA-256"):
        build_queue(receipts, audit)


def test_audit_unknown_registry_fails_closed():
    receipts, audit = _sources()
    audit["critical_mismatches"][0]["reg_number"] = "0348100024426000039"
    with pytest.raises(ValueError, match="absent"):
        build_queue(receipts, audit)


def test_source_inventory_cannot_be_empty():
    with pytest.raises(ValueError, match="nonempty"):
        build_queue({"cases": []}, {})
