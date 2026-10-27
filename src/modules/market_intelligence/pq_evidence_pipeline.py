"""Automated original-source PQ evidence triage, without fabricated awards."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import yaml

from .eis_coverage import SUBSYSTEM_DOCUMENTS, audit_day
from .eis_source_ledger import extract_archive, link_original_documents
from .eis_attachment_manifest import attachment_manifest


def triage(*, root: Path, ontology: Path, first: date, last: date,
           regions: list[str], subsystems: list[str],
           max_archives: int = 40) -> dict:
    if first > last or (last - first).days > 1200 or not 1 <= max_archives <= 200:
        raise ValueError("Invalid bounded evidence scope")
    if not regions or any(len(r) != 2 or not r.isdigit() for r in regions):
        raise ValueError("Invalid regions")
    if not subsystems or any(s not in SUBSYSTEM_DOCUMENTS for s in subsystems):
        raise ValueError("Invalid subsystems")
    terms = yaml.safe_load(ontology.read_text(encoding="utf-8"))
    if not isinstance(terms, dict) or not terms.get("families"):
        raise ValueError("Invalid PQ ontology")
    from .eis_soap_backfill import scan_archive

    records = []
    candidates = []
    attachment_counts = Counter()
    coverage = Counter()
    inspected = 0
    day = first
    while day <= last:
        for region in regions:
            for subsystem in subsystems:
                cell = audit_day(root, region, day, subsystem)
                coverage[cell["status"]] += 1
                if cell["status"] != "verified_day":
                    continue
                receipt_path = (root / subsystem / SUBSYSTEM_DOCUMENTS[subsystem]
                                / day.isoformat() / f"region-{region}.json")
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                for item in receipt["archives"]:
                    if inspected >= max_archives:
                        break
                    index = item["index"]
                    archive = (receipt_path.parent / f"region-{region}"
                               / f"archive-{index:03d}" / "documentation-archive.zip")
                    digest = item["archive_sha256"]
                    source = {"date": day.isoformat(), "region": region,
                              "subsystem": subsystem, "archive_sha256": digest}
                    originals = extract_archive(
                        archive, official_archive_sha256=digest,
                        subsystem=subsystem, region=region, exact_date=day.isoformat())
                    records.extend(originals)
                    scanned = scan_archive(archive, terms)
                    for hit in scanned["matches"]:
                        candidates.append({**hit, "source_day": source,
                                           "status": "lexical_candidate_needs_original_attachment"})
                    attachments = attachment_manifest(
                        archive_path=archive, official_archive_sha256=digest,
                        subsystem=subsystem, region=region, exact_date=day.isoformat())
                    attachment_counts["references"] += len(attachments.get("attachments", []))
                    attachment_counts["rejected"] += attachments.get("rejected_count", 0)
                    inspected += 1
        day += timedelta(days=1)
    linkage = link_original_documents(records)
    return {
        "schema_version": "pq-primary-evidence-triage/1",
        "scope": {"first": first.isoformat(), "last": last.isoformat(),
                  "regions": regions, "subsystems": subsystems,
                  "max_archives": max_archives},
        "source_day_status": dict(coverage),
        "archives_sha_verified_and_inspected": inspected,
        "primary_xml_records": len(records),
        "lexical_candidates": candidates,
        "attachment_reference_audit": dict(attachment_counts),
        "notice_protocol_linkage": linkage,
        "signed_awards_verified": False,
        "equipment_market_total_rub": None,
        "technical_attachment_content_inspected": False,
        "limitations": "XML-only lexical triage; download and read original annexes, verify signed contracts and resolve duplicates before market totals.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ontology", type=Path, required=True)
    parser.add_argument("--date-from", type=date.fromisoformat, required=True)
    parser.add_argument("--date-to", type=date.fromisoformat, required=True)
    parser.add_argument("--region", action="append", required=True)
    parser.add_argument("--subsystem", action="append", required=True)
    parser.add_argument("--max-archives", type=int, default=40)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = triage(root=args.root, ontology=args.ontology,
                    first=args.date_from, last=args.date_to,
                    regions=args.region, subsystems=args.subsystem,
                    max_archives=args.max_archives)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"archives": result["archives_sha_verified_and_inspected"],
                      "xml_records": result["primary_xml_records"],
                      "candidates": len(result["lexical_candidates"]),
                      "attachment_reference_audit": result["attachment_reference_audit"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
