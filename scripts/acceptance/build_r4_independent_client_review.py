"""Generate independent client-safe source review and machine audit separately.

No live EIS lookup, no LLM output or technical status strings in client report.
Input snapshots are private, pinned official evidence; output contains no raw
HTML, original attachments, secret URLs/UIDs or individual source bytes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.modules.tender_operator_agent_demo.r4_price_inquiry_primary_audit import (
    client_expert_source_report,
    reconcile_price_inquiry_originals,
)


def export_independent_review(
    output_dir: Path,
    *,
    official_original_directory: Path,
    source_matrix_path: Path | None = None,
) -> dict:
    matrix_source = source_matrix_path or (
        ROOT / "docs/acceptance/data/TDP_R4_20_LATER_BINARY_RECOVERY_2026-10-14.json"
    )
    machine = json.loads(matrix_source.read_text(encoding="utf8"))
    reconciled = reconcile_price_inquiry_originals(machine, official_original_directory)
    customer = client_expert_source_report(reconciled)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "tender-r4-independent-expert-client-report.md").write_text(
        customer, encoding="utf8"
    )
    (output_dir / "tender-r4-price-inquiry-original-source-audit.json").write_text(
        json.dumps(reconciled, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    return reconciled


def main() -> None:
    parser = argparse.ArgumentParser(description="Write source-proven critical R4 client report")
    parser.add_argument("--official-original-directory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    r = export_independent_review(
        args.output_dir, official_original_directory=args.official_original_directory
    )
    print(json.dumps({
        "source_records": r["summary"]["original_price_inquiry_cards_confirmed"],
        "original_documents": r["summary"]["price_inquiry_original_attachments_retrieved"],
        "human_reviews": r["summary"]["human_gold_reviews_completed"],
        "bid_ready": r["bid_ready"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
