"""Date/region/subsystem EIS SOAP coverage, never inferred from missing data.

Every verified cell proves only that the *requested date*, region, document
type and subsystem was successfully collected, SHA-checked and archive-scanned.
It does not prove EIS historical exhaustiveness, original awards or TAM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

SUBSYSTEM_DOCUMENTS = {
    "RI223": "purchaseNotice",
    "PRIZ": "epNotificationEF2020",
}
MAX_WINDOW_DAYS = 1200
MAX_REGIONS = 40


def _expected_path(root: Path, region: str, day: date, subsystem: str) -> Path:
    document_type = SUBSYSTEM_DOCUMENTS[subsystem]
    return root / subsystem / document_type / day.isoformat() / f"region-{region}.json"


def _reject_symlinks(root: Path, path: Path) -> None:
    if root.is_symlink():
        raise ValueError("Source root is symlinked")
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValueError("Source path escapes root") from exc
    check = root
    for part in relative.parts:
        check /= part
        if check.is_symlink():
            raise ValueError("Source path contains symlink")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_day(root: Path, region: str, day: date, subsystem: str) -> dict[str, Any]:
    """Verify one daily official XML ZIP receipt and each original ZIP digest."""
    if subsystem not in SUBSYSTEM_DOCUMENTS or not re.fullmatch(r"[0-9]{2}", region):
        raise ValueError("Invalid regime/region")
    path = _expected_path(root, region, day, subsystem)
    cell: dict[str, Any] = {
        "region": region,
        "date": day.isoformat(),
        "subsystem": subsystem,
        "document_type": SUBSYSTEM_DOCUMENTS[subsystem],
        "status": "missing",
        "sha_verified_archives": 0,
        "xml_documents_inspected": 0,
        "procurement_unique_count": None,
    }
    _reject_symlinks(root, path)
    if not path.exists():
        return cell
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict):
            raise TypeError("Invalid source receipt")
        for name, expected in (
            ("region", region),
            ("exact_date", day.isoformat()),
            ("subsystem", subsystem),
            ("document_type", SUBSYSTEM_DOCUMENTS[subsystem]),
        ):
            if receipt.get(name) != expected:
                raise ValueError(f"Receipt {name} does not match requested source")
        cell["provider_status"] = str(receipt.get("status", "unknown"))
        if (receipt.get("status") != "complete_with_archive_scan"
                or receipt.get("archive_scan_complete") is not True):
            cell["status"] = "incomplete"
            return cell
        archives = receipt.get("archives")
        archive_count = receipt.get("archive_count")
        if not isinstance(archives, list) or not isinstance(archive_count, int):
            raise TypeError("Missing official archive count")
        if not 0 <= archive_count <= 100 or len(archives) != archive_count:
            raise ValueError("Official archive count does not match receipt")
        for index, archive in enumerate(archives, 1):
            if not isinstance(archive, dict):
                raise TypeError("Invalid archive evidence record")
            if archive.get("index") != index:
                raise ValueError("Nonsequential archive position")
            saved = path.parent / f"region-{region}" / f"archive-{index:03d}" / "documentation-archive.zip"
            _reject_symlinks(root, saved)
            if not saved.is_file():
                raise ValueError("Original archive missing")
            recorded_sha = archive.get("archive_sha256")
            if not isinstance(recorded_sha, str) or not re.fullmatch(r"[a-f0-9]{64}", recorded_sha):
                raise ValueError("Invalid original archive SHA-256")
            if _hash_file(saved) != recorded_sha:
                raise ValueError("Original archive SHA-256 mismatch")
            documents = archive.get("xml_documents_inspected")
            if not isinstance(documents, int) or documents < 0 or documents > 10000:
                raise ValueError("Invalid XML inspection count")
            cell["sha_verified_archives"] += 1
            cell["xml_documents_inspected"] += documents
        cell["status"] = "verified_day"
        return cell
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        cell["status"] = "evidence_invalid"
        cell["integrity_error_type"] = type(exc).__name__
        cell["sha_verified_archives"] = 0
        cell["xml_documents_inspected"] = 0
        return cell


def summarize_coverage(
    *, root: Path, first: date, last: date, regions: list[str],
    subsystems: list[str],
) -> dict[str, Any]:
    if first > last or (last - first).days + 1 > MAX_WINDOW_DAYS:
        raise ValueError("Date interval must be 1..1200 days")
    if not regions or len(set(regions)) != len(regions) or len(regions) > MAX_REGIONS:
        raise ValueError("Regions must be unique and bounded")
    if any(not re.fullmatch(r"[0-9]{2}", region) for region in regions):
        raise ValueError("Invalid region code")
    if (not subsystems or len(set(subsystems)) != len(subsystems)
            or any(s not in SUBSYSTEM_DOCUMENTS for s in subsystems)):
        raise ValueError("Invalid or duplicate procurement subsystems")

    status = Counter()
    periods: dict[str, dict[str, Any]] = {}
    verified_archives = verified_xml = 0
    current = first
    while current <= last:
        for subsystem in subsystems:
            for region in regions:
                cell = audit_day(root, region, current, subsystem)
                key = f"{current:%Y-%m}|{subsystem}|{region}"
                month = periods.setdefault(key, {
                    "month": f"{current:%Y-%m}",
                    "subsystem": subsystem, "region": region,
                    "requested_days": 0, "verified_days": 0,
                    "missing_days": 0, "incomplete_days": 0,
                    "invalid_evidence_days": 0,
                })
                month["requested_days"] += 1
                status[cell["status"]] += 1
                if cell["status"] == "verified_day":
                    month["verified_days"] += 1
                    verified_archives += cell["sha_verified_archives"]
                    verified_xml += cell["xml_documents_inspected"]
                elif cell["status"] == "missing":
                    month["missing_days"] += 1
                elif cell["status"] == "incomplete":
                    month["incomplete_days"] += 1
                else:
                    month["invalid_evidence_days"] += 1
        current += timedelta(days=1)
    cells = (last - first).days + 1
    total_slots = cells * len(subsystems) * len(regions)
    assert sum(status.values()) == total_slots
    return {
        "schema_version": "mi-eis-source-coverage/0.1",
        "date_from": first.isoformat(), "date_to": last.isoformat(),
        "regions": regions, "subsystems": subsystems,
        "source_kind": "EIS_getDocsIP_region_day_notice",
        "total_source_day_slots": total_slots,
        "verified_day_slots": status["verified_day"],
        "missing_day_slots": status["missing"],
        "incomplete_day_slots": status["incomplete"],
        "invalid_evidence_day_slots": status["evidence_invalid"],
        "sha_verified_archives": verified_archives,
        "xml_documents_inspected_not_unique_tenders": verified_xml,
        "historical_exhaustiveness_verified": False,
        "winner_contracts_verified": False,
        "monthly": [periods[key] for key in sorted(periods)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only SHA-audited EIS source coverage")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--date-from", type=date.fromisoformat, required=True)
    parser.add_argument("--date-to", type=date.fromisoformat, required=True)
    parser.add_argument("--region", action="append", required=True)
    parser.add_argument("--subsystem", action="append", choices=sorted(SUBSYSTEM_DOCUMENTS), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = summarize_coverage(
        root=args.root, first=args.date_from, last=args.date_to,
        regions=args.region, subsystems=args.subsystem,
    )
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
