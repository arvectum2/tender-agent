"""Read-only independent SHA audit of EIS SOAP archives and sampled coverage.

This intentionally does *not* infer unique procedures, monthly source coverage,
winners, contractors, contract amounts, or demand from XML document counts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .eis_soap_backfill import MAX_ZIP_BYTES


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def audit_receipts(root: Path, *, attempt_date: str) -> dict[str, Any]:
    """Fail closed on missing/tampered ZIP or inconsistent receipt metadata."""
    if len(attempt_date) != 10 or not (
        attempt_date[:4].isdigit()
        and attempt_date[4] == "-"
        and attempt_date[5:7].isdigit()
        and attempt_date[7] == "-"
        and attempt_date[8:].isdigit()
    ):
        raise ValueError("attempt_date must be YYYY-MM-DD")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("source receipt directory missing or symlinked")
    if (root / "UNTRUSTED_REGION_COLLISION.json").exists():
        raise ValueError("unsafe legacy EIS archive root; SHA verification prohibited")
    rows: list[dict[str, Any]] = []
    for receipt_path in sorted(root.glob("*/*/*/region-*.json")):
        if receipt_path.is_symlink():
            raise ValueError("receipt symlinks are forbidden")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not str(receipt.get("attempt_utc", "")).startswith(attempt_date):
            continue
        if receipt.get("schema_version") != "mi-eis-soap-receipt/0.1":
            raise ValueError("unexpected EIS receipt schema")
        if receipt_path.name != f"region-{receipt.get('region')}.json":
            raise ValueError("receipt region and filename mismatch")
        if receipt_path.parent.name != receipt.get("exact_date"):
            raise ValueError("receipt date and path mismatch")
        if receipt_path.parent.parent.name != receipt.get("document_type"):
            raise ValueError("receipt document type and path mismatch")
        if receipt_path.parent.parent.parent.name != receipt.get("subsystem"):
            raise ValueError("receipt subsystem and path mismatch")
        archives = receipt.get("archives")
        complete = (
            receipt.get("status") == "complete_with_archive_scan"
            and receipt.get("archive_scan_complete") is True
        )
        if complete:
            if not isinstance(archives, list):
                raise ValueError("complete receipt has no archives")
            if receipt.get("archive_count") != len(archives):
                raise ValueError("inconsistent EIS archive count")
        xml_count = 0
        candidate_count = 0
        if complete:
            for expected_index, archive in enumerate(archives, start=1):
                if archive.get("index") != expected_index:
                    raise ValueError("archive indices missing or misordered")
                archive_path = (
                    receipt_path.parent / f"region-{receipt['region']}"
                    / f"archive-{expected_index:03d}" / "documentation-archive.zip"
                )
                if (
                    archive_path.is_symlink()
                    or archive_path.parent.is_symlink()
                    or archive_path.parent.parent.is_symlink()
                    or not archive_path.is_file()
                    or archive_path.stat().st_size > MAX_ZIP_BYTES
                ):
                    raise ValueError("ZIP missing, linked or exceeds size bound")
                if _sha256(archive_path) != archive.get("archive_sha256"):
                    raise ValueError("source ZIP SHA256 mismatch")
                count = archive.get("xml_documents_inspected")
                matches = archive.get("matches")
                if not isinstance(count, int) or count < 0 or not isinstance(matches, list):
                    raise ValueError("inconsistent XML scan receipt")
                xml_count += count
                candidate_count += len(matches)
        rows.append({
            "subsystem": receipt["subsystem"],
            "region": receipt["region"],
            "date": receipt["exact_date"],
            "status": receipt["status"],
            "archives_sha256_verified": len(archives) if complete else 0,
            "xml_documents_scanned": xml_count if complete else None,
            "lexical_candidate_occurrences": candidate_count if complete else None,
            "complete_archive_scan": complete,
        })
    rows.sort(key=lambda row: (row["date"], row["subsystem"], row["region"]))
    successful = [r for r in rows if r["complete_archive_scan"]]
    return {
        "schema_version": "mi-eis-source-sample-audit/0.1",
        "attempt_date": attempt_date,
        "sampled_source_region_days": len(rows),
        "verified_source_region_days": len(successful),
        "verified_zip_archives": sum(r["archives_sha256_verified"] for r in successful),
        "xml_documents_scanned": sum(r["xml_documents_scanned"] for r in successful),
        "lexical_candidate_occurrences": sum(
            r["lexical_candidate_occurrences"] for r in successful
        ),
        "national_or_monthly_coverage_established": False,
        "unique_procurements_established": False,
        "source_level": "EIS getDocsIP original archives; single sampled calendar days",
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="SHA-verify sampled EIS SOAP receipts")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--attempt-date", required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = audit_receipts(args.root, attempt_date=args.attempt_date)
    data = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(data, encoding="utf-8")
    print(data)


if __name__ == "__main__":
    main()
