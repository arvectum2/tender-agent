"""Export conservative R4 20-case source coverage from existing signed-off-by-none audits.

Read-only input: tracked historical R4/R5 CSVs, no EIS network calls.
Output: deterministic JSON plus flat human-review queue CSV; no original files
or human identifiers. These artifacts do not prove live bid eligibility.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.modules.tender_operator_agent_demo.r4_case_source_coverage import (  # noqa: E402
    build_r4_20_case_source_coverage,
)

SOURCES = {
    "protocol_markdown": "TDP_R4_R5_HUMAN_GOLD_PROTOCOL_2026-10-12.md",
    "independent_cases_csv": "TDP_R5_INDEPENDENT_20_CASES_2026-10-12.csv",
    "independent_files_csv": "TDP_R5_INDEPENDENT_168_FILES_2026-10-12.csv",
    "persisted_facts_csv": "TDP_R5_INDEPENDENT_PERSISTED_FACTS_20_2026-10-12.csv",
    "human_queue_csv": "TDP_R5_20_CASE_HUMAN_REVIEW_QUEUE_2026-10-11.csv",
}
CSV_COLUMNS = (
    "reg_number", "official_archive_status", "source_receipt_status",
    "source_case_file_count", "archived_original_xml_matched",
    "attached_non_xml_files", "independent_original_binary_transfers_verified",
    "historic_receipt_edition", "highest_observed_archived_edition",
    "persisted_report_exists", "persisted_deadline_check", "persisted_price_check",
    "human_source_review", "arv001_release_ready", "bid_ready", "blockers",
)


def export_matrix(output_dir: Path, *, acceptance_dir: Path | None = None) -> dict:
    acceptance = acceptance_dir or ROOT / "docs" / "acceptance"
    inputs = {
        key: (acceptance / name).read_text(encoding="utf-8")
        for key, name in SOURCES.items()
    }
    packet = build_r4_20_case_source_coverage(**inputs)
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("output destination is not a directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "r4-20-historical-source-coverage.json"
    csv_path = output_dir / "r4-20-historical-source-coverage.csv"
    json_path.write_text(
        json.dumps(packet, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for case in packet["cases"]:
            writer.writerow({
                k: "|".join(case.get(k) or []) if k == "blockers" else case.get(k)
                for k in CSV_COLUMNS
            })
    return packet


def main() -> None:
    parser = argparse.ArgumentParser(description="Build read-only historical R4 source review queue")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = export_matrix(args.output_dir)["summary"]
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
