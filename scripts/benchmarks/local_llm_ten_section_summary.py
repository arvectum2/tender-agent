"""Summarize completed original-document local LLM probes without rating truth."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def summarize(records: list[dict]) -> list[dict]:
    result = []
    for law in sorted({row["law"] for row in records}):
        cases = [row for row in records if row["law"] == law]

        def intact(row: dict) -> bool:
            return (
                bool(row.get("cited_uuids"))
                and not row.get("invalid_citations")
                and row.get("finish_reason") == "stop"
                and not row.get("error")
            )

        result.append(
            {
                "law": law,
                "cases": len(cases),
                "complete_with_source_ids": sum(intact(row) for row in cases),
                "uncited": sum(not row.get("cited_uuids") for row in cases),
                "changed_or_unknown_ids": sum(
                    bool(row.get("invalid_citations")) for row in cases
                ),
                "truncated_by_length": sum(
                    row.get("finish_reason") == "length" for row in cases
                ),
                "request_errors": sum(bool(row.get("error")) for row in cases),
                "duration_seconds": round(
                    sum(row.get("time_seconds", 0) for row in cases), 2
                ),
                "factual_accuracy": "NOT_ASSESSED_AUTOMATICALLY",
                "legal_conclusion": "NOT_ASSESSED",
                "decision": "NOT_DECIDED",
            }
        )
    return result


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: local_llm_ten_section_summary.py ORIGINAL_RESULTS_JSON"
        )
    rows = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(summarize(rows), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
