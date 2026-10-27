"""Recover missing 223-FZ attachments from SHA-verified EIS archive receipts.

Only official XML-bound attachment acquisition is allowed. Source candidates
without verified archive receipts are recorded as unresolved, never downloaded
from guessed URLs. The downloaded originals can then be processed by Data
Platform's existing document ingestion pipeline after authorization.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from .eis_attachment_acquisition import acquire_223fz_eis_attachments
from .eis_coverage import SUBSYSTEM_DOCUMENTS


def _atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8",
                                     prefix=".recovery-", delete=False) as f:
        tmp = Path(f.name)
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def verified_archive_candidates(root: Path, number: str, *, max_receipts: int = 250) -> list[dict]:
    """Locate validated archive receipts; actual XML number binding is rechecked by downloader."""
    if not number.isdigit() or len(number) != 11:
        return []
    subsystem = "RI223"
    base = root / subsystem / SUBSYSTEM_DOCUMENTS[subsystem]
    if not base.is_dir() or base.is_symlink():
        return []
    candidates = []
    receipts = sorted(base.glob("*/region-*.json"))
    if len(receipts) > max_receipts:
        receipts = receipts[:max_receipts]
    for receipt_path in receipts:
        if receipt_path.is_symlink():
            continue
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        region = receipt_path.stem.removeprefix("region-")
        day = receipt_path.parent.name
        for item in receipt.get("archives", []):
            if "archive_sha256" not in item or "index" not in item:
                continue
            archive = (receipt_path.parent / f"region-{region}" /
                       f"archive-{int(item['index']):03d}" / "documentation-archive.zip")
            if archive.is_file() and not archive.is_symlink():
                candidates.append({"archive": str(archive),
                                   "sha256": item["archive_sha256"],
                                   "region": region, "date": day})
    return candidates


def recover(*, gaps: Path, archive_root: Path, target_root: Path,
            journal: Path, max_cases: int = 3, max_archives: int = 12) -> dict:
    if not 1 <= max_cases <= 20 or not 1 <= max_archives <= 50:
        raise ValueError("Invalid recovery budget")
    cases = json.loads(gaps.read_text(encoding="utf-8"))["cases"]
    previous = json.loads(journal.read_text(encoding="utf-8")) if journal.exists() else {
        "schema_version": "pq-official-archive-recovery/1", "attempts": []}
    done = {row["procedure_id"] for row in previous["attempts"]
            if row.get("status") == "downloaded"}
    attempts = []
    for case in cases:
        if len(attempts) >= max_cases:
            break
        number = str(case.get("procedure_id", ""))
        if len(number) != 11 or not number.isdigit() or number in done:
            continue
        archives = verified_archive_candidates(archive_root, number)[:max_archives]
        record = {"procedure_id": number, "archives_checked": 0,
                  "status": "no_verified_archive_candidate", "downloaded_count": 0}
        for source in archives:
            record["archives_checked"] += 1
            try:
                outcome = acquire_223fz_eis_attachments(
                    registry_number=number, archive_path=Path(source["archive"]),
                    archive_sha256=source["sha256"], region=source["region"],
                    source_date=source["date"], target_dir=target_root / number,
                    max_attachments=8)
                if outcome.get("downloaded_count", 0):
                    record["status"] = "downloaded"
                    record["downloaded_count"] += outcome["downloaded_count"]
                    record["source_archive_sha256"] = source["sha256"]
                    break
                record["status"] = str(outcome.get("status", "no_matching_documents"))
            except (OSError, ValueError, RuntimeError) as exc:
                record["status"] = "source_error"
                record["error_type"] = type(exc).__name__
        previous["attempts"].append(record)
        attempts.append(record)
        _atomic(journal, previous)
    return {"cases_attempted": len(attempts),
            "documents_downloaded": sum(x["downloaded_count"] for x in attempts),
            "statuses": [x["status"] for x in attempts]}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gaps", type=Path, required=True)
    p.add_argument("--archive-root", type=Path, required=True)
    p.add_argument("--target-root", type=Path, required=True)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--max-cases", type=int, default=3)
    a = p.parse_args()
    print(json.dumps(recover(gaps=a.gaps, archive_root=a.archive_root,
                             target_root=a.target_root, journal=a.journal,
                             max_cases=a.max_cases), ensure_ascii=False))


if __name__ == "__main__":
    main()
