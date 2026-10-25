"""Bounded, resumable, explicit-execute historical EIS getDocsIP source scheduler.

This is NOT a national source completeness claim. A successful SOAP date/region
slot says nothing about the availability of attached EPC technical documents.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from .eis_coverage import SUBSYSTEM_DOCUMENTS, audit_day
from .eis_soap_backfill import collect

MAX_PLAN_DAYS = 1200
MAX_LIVE_CALLS = 12
MAX_REGIONS = 8


def _calendar_months(first: date, last: date) -> list[tuple[int, int]]:
    months = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def _spread_order(items: list[Any]) -> list[Any]:
    """Deterministic bisection gives broad historical temporal spread."""
    if not items:
        return []
    # Breadth-first bisection spreads small request budgets across the years.
    queue = [(0, len(items))]
    ordered = []
    while queue:
        start, end = queue.pop(0)
        if start >= end:
            continue
        mid = (start + end) // 2
        ordered.append(items[mid])
        queue.append((start, mid))
        queue.append((mid + 1, end))
    return ordered


def _month_days(year: int, month: int, first: date, last: date) -> list[date]:
    day = date(year, month, 1)
    dates = []
    while day.month == month:
        if first <= day <= last:
            dates.append(day)
        day += timedelta(days=1)
    return sorted(dates, key=lambda value: (abs(value.day - 15), value.day))


def plan_history(
    *, root: Path, first: date, last: date, regions: list[str],
    subsystems: list[str], max_calls: int = 4,
) -> dict[str, Any]:
    """Return a deterministic plan, inspecting receipts and ZIP SHA but no network."""
    if first > last or (last - first).days >= MAX_PLAN_DAYS:
        raise ValueError("Historical interval must be 1..1200 days")
    if not (1 <= max_calls <= MAX_LIVE_CALLS):
        raise ValueError("max_calls must be between 1 and 12")
    if not (1 <= len(regions) <= MAX_REGIONS) or len(set(regions)) != len(regions):
        raise ValueError("Invalid or duplicate region list")
    if not subsystems or len(set(subsystems)) != len(subsystems):
        raise ValueError("Empty or duplicate subsystem list")
    if any(item not in SUBSYSTEM_DOCUMENTS for item in subsystems):
        raise ValueError("Invalid EIS subsystem")
    if root.is_symlink() or (root / "UNTRUSTED_REGION_COLLISION.json").exists():
        raise ValueError("Legacy, symlinked or quarantined original archive root")

    months = _calendar_months(first, last)
    priority = _spread_order(months)
    cells: dict[tuple[int, int], list[dict[str, str]]] = {}
    status = Counter()
    verified_per_month = Counter()
    for month_index, (year, month) in enumerate(months):
        candidates = []
        # Rotate source/regime priority across months to prevent systematically
        # sampling only RI223 and one city under a small invocation budget.
        sources = [(region, subsystem) for region in regions for subsystem in subsystems]
        offset = month_index % len(sources)
        ordered_sources = sources[offset:] + sources[:offset]
        for day in _month_days(year, month, first, last):
            for region, subsystem in ordered_sources:
                evidence = audit_day(root, region, day, subsystem)
                kind = evidence["status"]
                status[kind] += 1
                if kind == "verified_day":
                    verified_per_month[(year, month)] += 1
                if kind == "evidence_invalid":
                    # Never silently overwrite apparently successful original
                    # source evidence with newly downloaded bytes.
                    raise ValueError("Invalid original EIS evidence: inspect archived receipt manually")
                if kind == "missing":
                    archive_staging = (
                        root / subsystem / SUBSYSTEM_DOCUMENTS[subsystem]
                        / day.isoformat() / f"region-{region}"
                    )
                    if archive_staging.exists() or archive_staging.is_symlink():
                        raise ValueError(
                            "Orphaned original archive staging without verified receipt"
                        )
                    candidates.append({
                        "region": region, "subsystem": subsystem,
                        "document_type": SUBSYSTEM_DOCUMENTS[subsystem],
                        "date": day.isoformat(),
                    })
                # 'incomplete' is deliberately left out of automatic
                # retry: may hide a partial download or transport failure.
        cells[(year, month)] = candidates

    selected: list[dict[str, str]] = []
    # One missing source-day per month per round, across wide temporal horizon.
    # Subsequent runs prioritize months with the fewest verified cells.
    month_priority = sorted(
        priority,
        key=lambda key: (verified_per_month[key], priority.index(key)),
    )
    round_index = 0
    while len(selected) < max_calls:
        advanced = False
        for year, month in month_priority:
            candidates = cells[(year, month)]
            if round_index < len(candidates):
                selected.append(candidates[round_index])
                advanced = True
                if len(selected) == max_calls:
                    break
        if not advanced:
            break
        round_index += 1

    return {
        "schema_version": "mi-eis-history-plan/0.1",
        "first": first.isoformat(), "last": last.isoformat(),
        "regions": regions, "subsystems": subsystems,
        "max_calls": max_calls, "selected": selected,
        "source_day_status": dict(status),
        "selected_calls": len(selected),
        "total_slots_examined": sum(status.values()),
        "dry_run": True,
        "original_provenance_required": True,
        "national_completeness_achieved": False,
        "unique_tenders_verified": False,
    }


def execute_plan(
    *, plan: dict[str, Any], root: Path, ontology: dict[str, Any],
    client: Any = None, minimum_pause_seconds: float = 1.0,
) -> list[dict[str, Any]]:
    """One deliberate bounded read-only batch; no token/URLs in output."""
    if not 0 <= minimum_pause_seconds <= 60:
        raise ValueError("Pause must be bounded")
    selected = plan["selected"]
    if len(selected) > MAX_LIVE_CALLS:
        raise ValueError("Live request budget exceeded")
    outcome: list[dict[str, Any]] = []
    for index, item in enumerate(selected):
        day = date.fromisoformat(item["date"])
        region, subsystem = item["region"], item["subsystem"]
        before = audit_day(root, region, day, subsystem)
        if before["status"] == "verified_day":
            outcome.append({**item, "status": "already_verified", "archives_sha256_checked": True})
            continue
        if before["status"] != "missing":
            outcome.append({**item, "status": "skipped_non_missing_source"})
            continue
        result = collect(
            regions=[region], first=day, last=day, root=root, ontology=ontology,
            max_requests=1, subsystem=subsystem,
            document_type=SUBSYSTEM_DOCUMENTS[subsystem],
            download_archives=True, client=client, force_retry=False,
        )
        saved = result[0] if result else {}
        after = audit_day(root, region, day, subsystem)
        state = after["status"]
        outcome.append({
            **item, "status": state,
            "soap_receipt_status": saved.get("status"),
            "sha_verified_archives": after.get("sha_verified_archives", 0),
            "xml_documents_inspected": after.get("xml_documents_inspected", 0),
        })
        if state == "evidence_invalid" or saved.get("status") == "retryable_network_failure":
            break
        if index < len(selected) - 1 and minimum_pause_seconds:
            time.sleep(minimum_pause_seconds)
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser(description="Audited bounded EIS history planner")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ontology", type=Path, required=True)
    parser.add_argument("--date-from", type=date.fromisoformat, required=True)
    parser.add_argument("--date-to", type=date.fromisoformat, required=True)
    parser.add_argument("--region", action="append", required=True)
    parser.add_argument("--subsystem", action="append", choices=sorted(SUBSYSTEM_DOCUMENTS), required=True)
    parser.add_argument("--max-calls", type=int, default=4)
    parser.add_argument("--execute", action="store_true",
                        help="Explicitly enable real EIS SOAP requests and source archive downloads")
    args = parser.parse_args()
    plan = plan_history(
        root=args.root, first=args.date_from, last=args.date_to,
        regions=args.region, subsystems=args.subsystem,
        max_calls=args.max_calls,
    )
    # Print only source scope and budget; never private SOAP envelope.
    print(json.dumps(plan, ensure_ascii=False))
    if args.execute:
        ontology = yaml.safe_load(args.ontology.read_text(encoding="utf-8"))
        for row in execute_plan(plan=plan, root=args.root, ontology=ontology):
            print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
