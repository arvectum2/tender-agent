"""Reconcile later private official filestore rechecks with original R4 CSV.

This is offline replay of pinned prior verified-TLS *receipts*, NOT a new
HTTPS download, current-EIS status or legal document-content verification.
Private UID / URL / raw binary manifests never appear in returned outputs.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from copy import deepcopy
from typing import Any

from scripts.acceptance.verify_eis_filestore_receipts import verify_full_recheck

PINNED_20261012_SOURCE_SHA256 = "4f453e12c0013a200422990bf65a96fdfc476be6eda2b69065d18115391d9822"
PINNED_20261012_RECHECK_SHA256 = "96a64d6d89f48478267bb2d976b241971f140ee2939e3478b82e3aef239acb82"


def attach_later_original_binary_receipts(
    historical_coverage: dict[str, Any],
    independent_168_files_csv: str,
    official_source_manifest_bytes: bytes,
    verified_recheck_manifest_bytes: bytes,
    *,
    expected_source_sha256: str = PINNED_20261012_SOURCE_SHA256,
    expected_recheck_sha256: str = PINNED_20261012_RECHECK_SHA256,
    required: int = 72,
) -> dict[str, Any]:
    """Accept receipt overlay only when pinned bytes, identities and counts match."""
    source_digest = hashlib.sha256(official_source_manifest_bytes).hexdigest()
    recheck_digest = hashlib.sha256(verified_recheck_manifest_bytes).hexdigest()
    if source_digest != expected_source_sha256 or recheck_digest != expected_recheck_sha256:
        raise ValueError("private recovery manifest digest is not the pinned archived receipt")
    if len(official_source_manifest_bytes) > 2_000_000 or len(verified_recheck_manifest_bytes) > 2_000_000:
        raise ValueError("private receipt exceeds audit limit")
    source = json.loads(official_source_manifest_bytes)
    verified = json.loads(verified_recheck_manifest_bytes)
    proof = verify_full_recheck(source, verified, required=required)
    prior_files = list(csv.DictReader(io.StringIO(independent_168_files_csv)))
    prior: dict[tuple[str, str], dict[str, str]] = {}
    for row in prior_files:
        if row["extension"] == ".xml":
            continue
        key = (row["reg_number"], row["file_id"].casefold())
        if key in prior:
            raise ValueError("original source inventory contains a repeated non-XML file ID")
        if row["cached_bytes_SHA_match"] != "YES" or row["attachment_UID_in_official_XML"] != "YES":
            raise ValueError("unverified historic source cannot be upgraded by later private receipt")
        prior[key] = row
    source_keys: set[tuple[str, str]] = set()
    recovered_by_case: dict[str, int] = {}
    for row in source["files"]:
        key = row["reg_number"], str(row.get("file_id") or "").casefold()
        old = prior.get(key)
        if key in source_keys or not old:
            raise ValueError("private filestore source has duplicate/foreign file ID")
        source_keys.add(key)
        if (old["historic_SHA256"] != row["stored_sha256"]
                or int(old["file_size_bytes"]) != row["stored_bytes"]):
            raise ValueError("private recovered source SHA/size conflicts with independently cached file receipt")
        recovered_by_case[row["reg_number"]] = recovered_by_case.get(row["reg_number"], 0) + 1
    if source_keys != set(prior):
        raise ValueError("private recovery overlay does not cover exact historic non-XML originals")
    if len(source_keys) != required or sum(recovered_by_case.values()) != required:
        raise ValueError("wrong private source recovery cardinality")
    if proof["downloaded_binaries_recorded_verified"] != required:
        raise ValueError("unverified latest filestore recovery")
    matrix = deepcopy(historical_coverage)
    if len(matrix.get("cases") or []) != 20:
        raise ValueError("latest recovery overlay expects canonical twenty R4 procurement cases")
    for case in matrix["cases"]:
        reg = case["reg_number"]
        newly_checked = recovered_by_case.get(reg, 0)
        if newly_checked != case["attached_non_xml_files"]:
            raise ValueError("case recovery count does not equal cached non-XML original inventory")
        case["later_20261012_verified_official_binary_recovery"] = newly_checked
        case["later_recovery_evidence_status"] = (
            "LATER_OFFICIAL_BINARY_RECEIPT_VERIFIED" if newly_checked
            else "NO_BINARY_ATTACHMENT_IN_HISTORIC_CASE"
        )
        # Early 2026-10-12 discrepancy is superseded by the *subsequent*
        # source-authenticated receipt recheck for exactly the same originals.
        if newly_checked:
            case["blockers"] = [
                flag for flag in case["blockers"]
                if flag != "OFFICIAL_ATTACHMENT_BINARY_RETRANSFER_NOT_CONFIRMED_IN_THIS_AUDIT"
            ]
            case["blockers"].append("RECOVERED_BINARY_CURRENT_NOTICE_REVISION_UNATTESTED")
            case["blockers"].sort()
        case["human_source_review"] = "NOT_VERIFIED"
        case["expert_gold"] = False
        case["latest_official_notice_attested"] = False
        case["arv001_release_ready"] = False
        case["bid_ready"] = False
    matrix["prior_historical_matrix_sha256"] = historical_coverage["source_matrix_sha256"]
    matrix["source_matrix_sha256"] = hashlib.sha256(
        json.dumps(matrix["cases"], sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    matrix["later_recovery"] = {
        "status": "PINNED_PRIVATE_RECEIPT_OFFLINE_REPLAY_NOT_LIVE_REDOWNLOAD",
        "source_manifest_sha256": source_digest,
        "recheck_manifest_sha256": recheck_digest,
        "verified_original_binaries": required,
        "verified_original_binary_bytes": proof["verified_bytes"],
        "procurements_with_binary_recovery": proof["unique_procurements"],
        "human_gold_attested": False,
        "live_current_notice_attested": False,
        "bid_ready": False,
    }
    matrix["summary"]["later_official_binary_receipts_reconciled"] = required
    matrix["summary"]["later_official_binary_bytes_reconciled"] = proof["verified_bytes"]
    matrix["summary"]["later_official_binary_case_count"] = proof["unique_procurements"]
    matrix["scope"] = "COMBINED_HISTORICAL_R4_ARCHIVE_WITH_PINNED_LATER_FILSTORE_RECEIPTS_NOT_LIVE"
    matrix["human_gold_attested"] = False
    matrix["bid_ready"] = False
    return matrix
