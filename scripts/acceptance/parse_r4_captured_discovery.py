"""Derive first-party HTML tender-card ranks; no legal text, SUT or EIS claims."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.modules.tender_operator_agent_demo.r4_discovery_html_parser import (
    parse_source_cards,
)
from src.modules.tender_operator_agent_demo.r4_discovery_snapshot_provenance import (
    check_live_discovery_evidence,
)
from src.modules.tender_operator_agent_demo.r4_prospective_sampling import (
    validate_sampling_intent,
)


def parse_captured_source_snapshots(
    *, intent: dict, capture_receipt: dict, captured_original_root: Path,
) -> dict:
    validate_sampling_intent(intent)
    pages = capture_receipt.get("pages")
    if not isinstance(pages, list) or len(pages) != len(intent["page_order"]):
        raise ValueError("Both registered source captures are required")
    snapshots = []
    for index, (page, url) in enumerate(zip(pages, intent["page_order"]), 1):
        if (
            page.get("url") != url
            or page.get("source_page_rank") != index
            or page.get("status") != "TLS_SHA_ORIGINAL_CAPTURED_NOT_YET_PARSED"
        ):
            raise ValueError("No verified raw HTML for registered source page")
        relative = Path(page["html_file"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe original-source path")
        content = (captured_original_root / relative).read_bytes()
        snapshots.append({
            "url": url,
            "status": "SOURCE_FETCH_VERIFIED",
            "captured_at_utc": page["capture_started_at_utc"],
            "source_capture_sha256": page["content_sha256"],
            "rows": parse_source_cards(content),
        })
    proof = check_live_discovery_evidence(
        intent=intent,
        capture_receipt=capture_receipt,
        captured_original_root=captured_original_root,
        parsed_snapshots=snapshots,
    )
    return {
        "capture_receipt_sha256": proof,
        "selection_intent_sha256": intent["immutable_intent_sha256"],
        "source_only": True,
        "no_sut_or_legal_gold": True,
        "parsed_snapshots": snapshots,
        "summary_by_page": [
            {
                "source_page_rank": i + 1,
                "visible_tenders": len(page["rows"]),
                "source_cards_44fz": sum(x["law"] == "44-ФЗ" for x in page["rows"]),
                "source_cards_223fz": sum(x["law"] == "223-ФЗ" for x in page["rows"]),
            }
            for i, page in enumerate(snapshots)
        ],
        "official_eis_zip_xml_and_originals_verified": 0,
        "independent_expert_gold": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registered-intent", type=Path, required=True)
    parser.add_argument("--tls-capture-receipt", type=Path, required=True)
    parser.add_argument("--captured-original-root", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args()
    if args.private_output.exists():
        raise ValueError("Never overwrite an earlier selected original HTML parsing receipt")
    result = parse_captured_source_snapshots(
        intent=json.loads(args.registered_intent.read_text()),
        capture_receipt=json.loads(args.tls_capture_receipt.read_text()),
        captured_original_root=args.captured_original_root,
    )
    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("PARSED_FIRST_PARTY_HTML_PAGES", len(result["parsed_snapshots"]))
    for row in result["summary_by_page"]:
        print("PAGE_SOURCE_ONLY", row["source_page_rank"], row["visible_tenders"],
              row["source_cards_44fz"], row["source_cards_223fz"])
    print("OFFICIAL_CASES_AND_HUMAN_GOLD", 0, 0)


if __name__ == "__main__":
    main()
