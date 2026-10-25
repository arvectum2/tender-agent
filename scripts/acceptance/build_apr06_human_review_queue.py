"""Render a human-review queue from explicitly supplied APR-06 metadata receipts.

The output is a *checklist*, never a completed review. All human verdicts
stay blank regardless of any model-generated audit or machine decision.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

COLUMNS = (
    "reg_number",
    "machine_run_status",
    "file_count",
    "hashed_file_count",
    "notice_sha256",
    "archive_download_status",
    "machine_revision_mismatch_flag",
    "source_receipt_operator_reviewed",
    "source_receipt_revision_human_verified",
    "current_official_notice_revision",
    "original_binary_eis_verified",
    "document_completeness_human_checked",
    "source_fact_citations_human_checked",
    "human_go_no_go_defer",
    "human_reviewer",
    "human_review_timestamp",
    "human_signoff_reference",
)

SHA256 = re.compile(r"[0-9a-fA-F]{64}")
REGISTRY = re.compile(r"(?:\d{11}|\d{19})")


def _sha(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = str(value)
    if not SHA256.fullmatch(text):
        raise ValueError("Invalid SHA-256 digest in source receipt")
    return text.lower()


def build_queue(receipts: dict[str, Any], machine_audit: dict[str, Any]) -> list[dict[str, Any]]:
    cases = receipts.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Receipts cases must be a nonempty list")
    audit_cases = machine_audit.get("critical_mismatches", [])
    if not isinstance(audit_cases, list):
        raise TypeError("Audit critical_mismatches must be a list")
    flagged: set[str] = set()
    for case in audit_cases:
        if not isinstance(case, dict) or not REGISTRY.fullmatch(str(case.get("reg_number", ""))):
            raise ValueError("Invalid machine audit registry number")
        flagged.add(str(case["reg_number"]))
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise TypeError("Invalid receipt record")
        number = str(case.get("reg_number", ""))
        if not REGISTRY.fullmatch(number) or number in seen:
            raise ValueError("Invalid or duplicated registry number in source receipt")
        seen.add(number)
        docs = case.get("document_files")
        if not isinstance(docs, list):
            raise TypeError("Missing original document file inventory")
        hashed = 0
        for item in docs:
            if not isinstance(item, dict):
                raise TypeError("Invalid document receipt")
            digest = _sha(item.get("sha256"))
            if digest:
                hashed += 1
        if case.get("operator_reviewed") is not False or case.get("official_notice_revision_verified_by_human") is not False:
            # A new human review must live in an independent signed record,
            # not silently be imported from a machine receipt.
            raise ValueError("Receipts unexpectedly claim human review; manually verify provenance")
        output.append(
            {
                "reg_number": number,
                "machine_run_status": str(case.get("status") or ""),
                "file_count": len(docs),
                "hashed_file_count": hashed,
                "notice_sha256": _sha(case.get("notice_sha256")),
                "archive_download_status": str(case.get("archive_download_status") or ""),
                "machine_revision_mismatch_flag": (
                    "MACHINE_REVIEW_FLAG" if number in flagged else ""
                ),
                "source_receipt_operator_reviewed": "false",
                "source_receipt_revision_human_verified": "false",
                "current_official_notice_revision": "",
                "original_binary_eis_verified": "",
                "document_completeness_human_checked": "",
                "source_fact_citations_human_checked": "",
                "human_go_no_go_defer": "",
                "human_reviewer": "",
                "human_review_timestamp": "",
                "human_signoff_reference": "",
            }
        )
    if flagged - seen:
        raise ValueError("Machine audit references a registry absent from receipt inventory")
    return sorted(output, key=lambda case: case["reg_number"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--machine-audit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-cases", type=int, default=0)
    args = parser.parse_args()
    rows = build_queue(
        json.loads(args.receipts.read_text(encoding="utf-8")),
        json.loads(args.machine_audit.read_text(encoding="utf-8")),
    )
    if args.expected_cases and len(rows) != args.expected_cases:
        raise SystemExit("Source case count differs from --expected-cases")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"REVIEW_QUEUE_PREPARED cases={len(rows)} files={sum(row['file_count'] for row in rows)} "
        f"hashed={sum(row['hashed_file_count'] for row in rows)} "
        f"human_signed=0 source_validation=not_done"
    )


if __name__ == "__main__":
    main()
