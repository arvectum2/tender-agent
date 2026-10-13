"""Offline coverage audit for private verified-TLS EIS filestore recheck receipts.

This checks identity, completeness, recorded transport results and exact sizes.
It does NOT download files or independently prove prior HTTPS sessions.
Never commit either input JSON: source identifiers and original receipts stay local.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

UID = re.compile(r"[A-Fa-f0-9]{32}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
MAX_FILE_BYTES = 30 * 1024 * 1024


def verify_full_recheck(source: dict, evidence: dict, *, required: int = 72) -> dict:
    if not isinstance(source, dict) or not isinstance(evidence, dict):
        raise TypeError("invalid_manifest_types")
    originals = source.get("files")
    results = evidence.get("results")
    if (not isinstance(originals, list) or not isinstance(results, list)
            or len(originals) != required or len(results) != required):
        raise ValueError("incomplete_source_or_recheck_receipts")
    before: dict[str, dict] = {}
    after: dict[str, dict] = {}
    for row in originals:
        if not isinstance(row, dict):
            raise TypeError("invalid_source_entry")
        uid = row.get("official_file_uid")
        signature = row.get("stored_sha256")
        bytes_expected = row.get("stored_bytes")
        if (not isinstance(uid, str) or not UID.fullmatch(uid)
                or not isinstance(signature, str) or not SHA256.fullmatch(signature)
                or type(bytes_expected) is not int or not 0 < bytes_expected <= MAX_FILE_BYTES
                or row.get("uid_in_official_archive_xml") is not True
                or not isinstance(row.get("reg_number"), str)
                or len(row["reg_number"]) != 19 or not row["reg_number"].isdigit()
                or uid in before):
            raise ValueError("invalid_or_duplicate_official_source_identity")
        before[uid] = row
    for row in results:
        if not isinstance(row, dict):
            raise TypeError("invalid_recheck_entry")
        uid = row.get("uid")
        if not isinstance(uid, str) or not UID.fullmatch(uid) or uid in after:
            raise ValueError("invalid_or_duplicate_recheck_identity")
        after[uid] = row
    if before.keys() != after.keys():
        raise ValueError("source_recheck_uid_set_mismatch")
    total_bytes = 0
    for uid, row in before.items():
        verified = after[uid]
        if (verified.get("reg_number") != row["reg_number"]
                or verified.get("result") != "verified"
                or verified.get("sha256_equal") is not True
                or verified.get("size_equal") is not True
                or verified.get("source_binary_verified") is not True
                or type(verified.get("actual_bytes")) is not int
                or verified["actual_bytes"] != row["stored_bytes"]):
            raise ValueError("unverified_or_mismatched_retrieved_binary")
        total_bytes += row["stored_bytes"]
    return {
        "scope": "OFFLINE_RECEIPT_COMPLETENESS_NOT_SECOND_NETWORK_RETRIEVAL",
        "source_xml_uid_anchors": len(before),
        "downloaded_binaries_recorded_verified": len(after),
        "verified_bytes": total_bytes,
        "unique_procurements": len({x["reg_number"] for x in originals}),
        "invalid_or_missing": 0,
        "live_dp_original_identity_verified": False,
        "human_owner_approved": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-audit", required=True, type=Path)
    parser.add_argument("--verified-batch", required=True, type=Path)
    parser.add_argument("--expected", type=int, default=72)
    args = parser.parse_args()
    if args.expected < 1 or args.expected > 200:
        raise SystemExit("invalid_expected_count")
    source_bytes = args.source_audit.read_bytes()
    evidence_bytes = args.verified_batch.read_bytes()
    if len(source_bytes) > 2_000_000 or len(evidence_bytes) > 2_000_000:
        raise SystemExit("manifest_too_large")
    output = verify_full_recheck(json.loads(source_bytes), json.loads(evidence_bytes),
                                 required=args.expected)
    output["source_manifest_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    output["recheck_manifest_sha256"] = hashlib.sha256(evidence_bytes).hexdigest()
    print(json.dumps(output, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
