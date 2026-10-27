"""Independently audit original EIS source-day receipts; no market extrapolation."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from .eis_coverage import SUBSYSTEM_DOCUMENTS, audit_day


def audit_window(*, root: Path, first: date, last: date,
                 regions: list[str], subsystems: list[str]) -> dict:
    if first > last or (last - first).days > 1200:
        raise ValueError("Invalid bounded interval")
    if not regions or not subsystems or len(regions) > 8:
        raise ValueError("Invalid source scope")
    if any(x not in SUBSYSTEM_DOCUMENTS for x in subsystems):
        raise ValueError("Unsupported subsystem")
    status = Counter()
    totals = Counter()
    verified = []
    day = first
    while day <= last:
        for region in regions:
            for subsystem in subsystems:
                item = audit_day(root, region, day, subsystem)
                status[item["status"]] += 1
                if item["status"] == "evidence_invalid":
                    raise ValueError("Invalid original archive evidence")
                if item["status"] == "verified_day":
                    totals["sha_verified_archives"] += item["sha_verified_archives"]
                    totals["xml_documents_inspected"] += item["xml_documents_inspected"]
                    verified.append({
                        "date": day.isoformat(), "region": region,
                        "subsystem": subsystem,
                        "sha_verified_archives": item["sha_verified_archives"],
                        "xml_documents_inspected": item["xml_documents_inspected"],
                    })
        day += timedelta(days=1)
    return {
        "schema_version": "pq-eis-source-audit/1",
        "window": [first.isoformat(), last.isoformat()],
        "regions": regions, "subsystems": subsystems,
        "source_day_status": dict(status),
        "verified_totals": dict(totals),
        "verified_source_days": verified,
        "unique_procurements": None,
        "confirmed_winners": None,
        "signed_contract_total_rub": None,
        "market_total_rub": None,
        "coverage_is_representative": False,
        "caveat": "Verified source-day ZIP/XML counts are not unique procurements, signed awards, PQ-specific demand or national market totals.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--date-from", type=date.fromisoformat, required=True)
    parser.add_argument("--date-to", type=date.fromisoformat, required=True)
    parser.add_argument("--region", action="append", required=True)
    parser.add_argument("--subsystem", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_window(root=args.root, first=args.date_from, last=args.date_to,
                          regions=args.region, subsystems=args.subsystem)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("source_day_status", "verified_totals")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
