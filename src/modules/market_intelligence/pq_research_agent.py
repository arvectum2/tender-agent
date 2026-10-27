"""Bounded, resumable Power Quality research agent using existing MI-013 tools.

No LLM-based winner inference. Public EIS 223 attachments are fetched only
when a SHA-verified original notice supplies exact registry number and GUID.
Data Platform ingestion remains an authenticated separate step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date
from pathlib import Path

from .eis_coverage import SUBSYSTEM_DOCUMENTS, audit_day
from .eis_source_ledger import extract_archive
from .eis_attachment_acquisition import acquire_223fz_eis_attachments


def _write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def run_agent(*, source_root: Path, output: Path, day: date, region: str,
              subsystem: str = "RI223", max_notices: int = 2,
              execute: bool = False, downloader=None) -> dict:
    if not (len(region) == 2 and region.isdigit()) or subsystem not in SUBSYSTEM_DOCUMENTS:
        raise ValueError("Invalid source selector")
    if not 1 <= max_notices <= 20 or source_root.is_symlink() or output.is_symlink():
        raise ValueError("Unsafe research budget or path")
    cell = audit_day(source_root, region, day, subsystem)
    if cell["status"] != "verified_day":
        return {"status": "source_not_verified", "source_day": cell, "executed": False}
    receipt_path = (source_root / subsystem / SUBSYSTEM_DOCUMENTS[subsystem]
                    / day.isoformat() / f"region-{region}.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    discovered = {}
    for item in receipt["archives"]:
        index = item["index"]
        archive = receipt_path.parent / f"region-{region}" / f"archive-{index:03d}" / "documentation-archive.zip"
        originals = extract_archive(
            archive, official_archive_sha256=item["archive_sha256"],
            subsystem=subsystem, region=region, exact_date=day.isoformat())
        for row in originals:
            number = row.get("notice_number")
            if row["record_kind"] == "notice" and number and len(number) == 11:
                discovered.setdefault(number, {
                    "registry_number": number, "archive": archive,
                    "sha": item["archive_sha256"], "original_xml_sha": row["source"]["xml_sha256"],
                })
    selected = [discovered[n] for n in sorted(discovered)[:max_notices]]
    results = []
    for item in selected:
        identity = hashlib.sha256((item["registry_number"] + item["sha"]).encode()).hexdigest()[:20]
        journal = output / "receipts" / f"{identity}.json"
        if journal.exists():
            saved = json.loads(journal.read_text(encoding="utf-8"))
            if saved.get("source_sha256") != item["sha"]:
                raise ValueError("Resume source SHA mismatch")
            results.append(saved)
            continue
        record = {
            "registry_number": item["registry_number"],
            "source_sha256": item["sha"],
            "original_xml_sha256": item["original_xml_sha"],
            "status": "planned_not_downloaded",
            "winner_verified": False,
            "contract_price_verified": False,
            "data_platform_ingested": False,
        }
        if execute:
            if subsystem != "RI223":
                raise ValueError("Only RI223 acquisition supported by this agent")
            fetch = downloader or acquire_223fz_eis_attachments
            result = fetch(
                registry_number=item["registry_number"],
                archive_path=item["archive"], archive_sha256=item["sha"],
                region=region, source_date=day.isoformat(),
                target_dir=output / "documents" / identity, max_attachments=8)
            record["status"] = result["status"]
            record["downloaded_count"] = result["downloaded_count"]
            record["download_receipt"] = result
            _write_atomic(journal, record)
        results.append(record)
    summary = {
        "schema_version": "pq-research-agent/1",
        "source_day": cell,
        "discovered_notices": len(discovered),
        "selected_notices": len(selected),
        "executed": execute,
        "records": results,
        "market_total_rub": None,
        "next_stage": "verified_original_attachment_text_and_authenticated_data_platform_ingest",
    }
    _write_atomic(output / "last_run.json", summary)
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--date", type=date.fromisoformat, required=True)
    p.add_argument("--region", required=True)
    p.add_argument("--subsystem", default="RI223")
    p.add_argument("--max-notices", type=int, default=2)
    p.add_argument("--execute", action="store_true")
    a = p.parse_args()
    result = run_agent(source_root=a.source_root, output=a.output, day=a.date,
                       region=a.region, subsystem=a.subsystem,
                       max_notices=a.max_notices, execute=a.execute)
    print(json.dumps({"status": result.get("status", "ok"),
                      "discovered": result.get("discovered_notices", 0),
                      "selected": result.get("selected_notices", 0),
                      "executed": result["executed"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
