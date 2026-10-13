"""Rehash saved APR-06 EIS files offline; byte-integrity != official EIS currentness.

Reads pre-existing receipts and source-run input files only. No network, no database,
no ETP actions or human approvals. Source blobs never leave the operator's machine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RUN = re.compile(r"toa-run-[0-9]{14}-[a-f0-9]{6}\Z")
_REG = re.compile(r"[0-9]{19}\Z")
_MAX_BLOB_BYTES = 100_000_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_saved_bytes(
    manifest: dict[str, Any],
    runs_root: Path,
    *,
    checked_at: datetime,
    manifest_sha256: str,
) -> dict[str, Any]:
    """Compare original saved input bytes with pre-existing manifest, fail closed."""
    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise ValueError("checked_at requires timezone")
    if manifest.get("schema_version") != "apr06-readonly-receipts-v1":
        raise ValueError("Unexpected APR06 manifest schema")
    if not _SHA.fullmatch(manifest_sha256):
        raise ValueError("Invalid manifest digest")
    if not runs_root.is_dir() or runs_root.is_symlink():
        raise ValueError("Valid non-symlink runs root required")

    summary = Counter()
    cases: list[dict[str, Any]] = []
    seen_reg: set[str] = set()
    seen_run: set[str] = set()
    for case in manifest.get("cases", []):
        reg, run = case.get("reg_number"), case.get("run_id")
        if not isinstance(reg, str) or not _REG.fullmatch(reg):
            raise ValueError("Invalid registry number")
        if not isinstance(run, str) or not _RUN.fullmatch(run):
            raise ValueError("Invalid run ID")
        if reg in seen_reg or run in seen_run:
            raise ValueError("Duplicate procurement or run ID")
        seen_reg.add(reg)
        seen_run.add(run)

        expected = case.get("document_files")
        if not isinstance(expected, list):
            raise ValueError("Missing original document_files list")
        expected_keys: set[tuple[str, int]] = set()
        for item in expected:
            if not isinstance(item, dict) or not isinstance(item.get("sha256"), str):
                raise ValueError("Malformed receipt entry")
            digest, size = item["sha256"], item.get("bytes")
            if not _SHA.fullmatch(digest) or not isinstance(size, int) or size <= 0:
                raise ValueError("Malformed digest or file size")
            if (digest, size) in expected_keys:
                raise ValueError("Duplicate expected original byte hash")
            expected_keys.add((digest, size))

        run_path = runs_root / run
        run_present = run_path.is_dir() and not run_path.is_symlink()
        input_path = run_path / "input"
        observed: set[tuple[str, int]] = set()
        scanned = 0
        if run_present and input_path.is_dir() and not input_path.is_symlink():
            for current, subdirs, names in os.walk(input_path, followlinks=False):
                base = Path(current)
                if any((base / d).is_symlink() for d in subdirs):
                    raise ValueError("Symlinked original source directory rejected")
                for name in names:
                    source = base / name
                    if source.is_symlink():
                        raise ValueError("Symlinked original source file rejected")
                    if not source.is_file():
                        continue
                    size = source.stat().st_size
                    if size > _MAX_BLOB_BYTES:
                        # This will remain missing if an expected file is oversized.
                        summary["oversized_unscanned"] += 1
                        continue
                    scanned += 1
                    observed.add((_sha256(source), size))

        matched = len(expected_keys & observed)
        missing = len(expected_keys) - matched
        state = (
            "NO_SOURCE_BYTES_RECORDED" if not expected
            else "SAVED_BYTES_MATCH" if missing == 0
            else "SAVED_BYTES_MISSING_OR_CHANGED"
        )
        cases.append({
            "reg_number": reg,
            "run_id": run,
            "archived_receipt_file_count": len(expected),
            "sha256_and_size_matched": matched,
            "not_matched": missing,
            "run_directory_present": run_present,
            "saved_input_files_scanned": scanned,
            "byte_integrity_state": state,
            "official_live_eis_revision_verified": False,
            "complete_attachment_set_verified": False,
            "human_procurement_reviewed": False,
        })
        summary["cases"] += 1
        summary["run_directories_present"] += int(run_present)
        summary["receipt_file_count"] += len(expected)
        summary["bytes_matched_count"] += matched
        summary["bytes_not_matched_count"] += missing
        summary["source_empty_cases"] += int(not expected)
        summary["cases_with_all_recorded_bytes_matched"] += int(bool(expected) and missing == 0)

    return {
        "schema_version": "apr06-saved-byte-integrity-v1",
        "checked_at": checked_at.isoformat(),
        "original_receipt_manifest_sha256": manifest_sha256,
        "source_receipts_capture_time": manifest.get("captured_at"),
        "scope": "OFFLINE_ARCHIVED_BYTES_ONLY_NOT_LIVE_EIS_STATUS",
        "network_access_required": False,
        "legal_or_commercial_acceptance": False,
        "human_signed_reviews": 0,
        "summary": dict(summary),
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--runs-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New output file only")
    parser.add_argument("--checked-at", required=True, help="ISO timestamp with offset")
    args = parser.parse_args()
    raw = args.manifest.read_bytes()
    report = audit_saved_bytes(
        json.loads(raw),
        args.runs_root,
        checked_at=datetime.fromisoformat(args.checked_at),
        manifest_sha256=hashlib.sha256(raw).hexdigest(),
    )
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(report, target, ensure_ascii=False, indent=2)
        target.write("\n")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
