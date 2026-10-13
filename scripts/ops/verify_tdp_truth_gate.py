"""Fail-closed human evidence review gate for Tender Agent R5.

The tool checks recorded reviews; it cannot independently establish that human
reviewers were correct. It never promotes model statements to source facts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.ops.audit_tdp_eis_corpus import audit_corpus

FIELDS = ("subject", "deadline", "price", "technical_requirements", "contract_risks")
OUTCOMES = {"correct", "incorrect", "not_applicable", "not_in_sources"}


def evaluate_gate(corpus: dict[str, Any], reviews: list[dict[str, Any]], minimum: int = 20) -> dict[str, Any]:
    if minimum < 20:
        raise ValueError("R5 minimum cannot be lowered below 20 procurements")
    selected = {r["procurement_number"]: r for r in corpus.get("procurements", [])}
    passed: set[str] = set()
    rejected: dict[str, list[str]] = {}
    for index, row in enumerate(reviews):
        if not isinstance(row, dict):
            rejected[f"row-{index}"] = ["invalid_row"]
            continue
        number = row.get("procurement_number")
        key = str(number) if number is not None else f"row-{index}"
        source = selected.get(key)
        why: list[str] = []
        if key in passed or key in rejected:
            why.append("duplicate_procurement")
        if source is None or row.get("run_id") != source.get("run_id"):
            why.append("missing_or_mismatched_corpus_run")
        elif not (source.get("file_count", 0) > 0
                  and source.get("file_count") == source.get("original_files_present")
                  == source.get("files_marked_extracted")
                  and source.get("report_available")):
            why.append("incomplete_original_files_or_report")
        if not isinstance(row.get("reviewer"), str) or len(row["reviewer"].strip()) < 3:
            why.append("human_reviewer_required")
        if not isinstance(row.get("reviewed_at"), str) or not row["reviewed_at"].strip():
            why.append("review_date_required")
        if row.get("human_approved") is not True:
            why.append("human_approval_required")
        checks = row.get("checks") if isinstance(row.get("checks"), dict) else {}
        for field in FIELDS:
            item = checks.get(field)
            if not isinstance(item, dict) or item.get("outcome") not in OUTCOMES:
                why.append(f"{field}_review_missing")
                continue
            if item["outcome"] == "incorrect":
                why.append(f"{field}_incorrect")
            if item["outcome"] == "correct" and not (
                isinstance(item.get("file_id"), str) and item["file_id"].strip()
                and isinstance(item.get("source_locator"), str) and item["source_locator"].strip()
            ):
                why.append(f"{field}_source_missing")
            if item["outcome"] == "not_in_sources" and field in FIELDS[:3] and item.get("model_value") not in ("UNKNOWN", None):
                why.append(f"{field}_unsourced_claim")
        if why:
            rejected[key] = why
        else:
            passed.add(key)
    return {
        "contract": "tdp-r5-human-truth-gate-v1",
        "pass": len(passed) >= minimum,
        "minimum": minimum,
        "reviewed_unique": len(passed),
        "candidate_reviews": len(reviews),
        "rejected": len(rejected),
        "warning": "Human attestations and source locators require independent audit.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.reviews.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        manifest = {}
    raw = manifest.get("reviews", []) if isinstance(manifest, dict) else []
    result = evaluate_gate(audit_corpus(args.runs_root), raw if isinstance(raw, list) else [])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
