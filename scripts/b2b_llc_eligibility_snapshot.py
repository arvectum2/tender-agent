"""Produce deterministic read-only LLC lead screening from pinned original receipts."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.tender_research.corporate_lead_gate import qualify_llc_response

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "docs" / "roadmap"


def build_snapshot(as_of: datetime, *, source_dir: Path = SOURCES) -> dict:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must include UTC offset")
    four_file = source_dir / "b2b_workspace_four_original_fit_2026-10-17.json"
    schlam_file = source_dir / "b2b_schlam_19006_original_offer_qa_2026-10-17.json"
    four = json.loads(four_file.read_text(encoding="utf-8"))
    schlam = json.loads(schlam_file.read_text(encoding="utf-8"))
    items = []
    for case in four["cases"]:
        items.append({
            "id": case["id"],
            "source_url": case["source_url"],
            "platform_status": case["original_public_status"],
            "organizer_type": case["original_public_organizer_type"],
            "submission_deadline": case["original_public_deadline_date"],
            "source_observed_at": case["checked_at_utc"],
            "source_html_sha256": case["original_html_sha256"],
            "source_http_status": case["original_http_status"],
            "receipt_file": four_file.name,
            "source_requirement_gate": case["conservative_qualification_gate"],
        })
    s = schlam["original_workspace_card"]
    items.append({
        "id": "19006",
        "source_url": s["url"],
        "platform_status": s["status"],
        "organizer_type": s["organizer_type"],
        "submission_deadline": s["deadline_date"],
        "source_observed_at": schlam["checked_at_utc"],
        "source_html_sha256": s["original_html_sha256"],
        "source_http_status": None,  # original card receipt has no explicit HTTP status
        "receipt_file": schlam_file.name,
        "source_requirement_gate": "PREPARED_OFFER_ONLY_ELIGIBILITY_AND_PAID_ACCESS_UNKNOWN",
    })
    if len({x["id"] for x in items}) != len(items):
        raise ValueError("duplicate original platform lead identifier")
    results = []
    for lead in sorted(items, key=lambda x: (x["submission_deadline"], x["id"])):
        decision = qualify_llc_response(
            lead,
            checked_at=as_of,
            source_sha256=lead["source_html_sha256"],
            source_http_status=lead["source_http_status"],
        )
        results.append({
            "id": lead["id"], "source_url": lead["source_url"],
            "public_deadline_date_only": lead["submission_deadline"],
            "source_observed_at": lead["source_observed_at"],
            "source_html_sha256": lead["source_html_sha256"],
            "receipt_file": lead["receipt_file"],
            "source_requirement_gate": lead["source_requirement_gate"],
            "eligibility_state": decision.state,
            "unresolved_gates": list(decision.blockers),
            "response_authorized": decision.response_authorized,
        })
    return {
        "schema_version": "1.0",
        "as_of": as_of.isoformat(),
        "scope": "original_public_snapshots_not_authenticated_company_bid_access",
        "source_status_freshness_hours": 48,
        "original_case_count": len(results),
        "company_qualified_to_respond_count": 0,
        "actual_replies_or_paid_actions": 0,
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", required=True, help="ISO timestamp with explicit offset")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    content = json.dumps(build_snapshot(datetime.fromisoformat(args.as_of)), indent=2, ensure_ascii=False) + "\n"
    args.output.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
