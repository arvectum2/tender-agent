"""Audit local LLM outputs against the exact provided chunk IDs.

This is an evidence-integrity guard, not a semantic accuracy or legal score.
Run: python scripts/benchmarks/local_llm_citation_audit.py path/to/results.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_UUID = re.compile(
    r"(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])",
    re.IGNORECASE,
)


def audit_entry(item: dict) -> dict:
    available = set(item.get("context_chunk_ids") or [])
    answer = str(item.get("answer") or "")
    cited = _UUID.findall(answer)
    invalid = sorted(set(cited).difference(available))
    tokens = (item.get("usage") or {}).get("completion_tokens")
    return {
        "law": item.get("law"),
        "registry": item.get("registry"),
        "model": item.get("model"),
        "supplied_chunks": len(available),
        "cited_chunk_ids": cited,
        "invalid_chunk_ids": invalid,
        "citation_integrity": (
            "INVALID_SOURCE_CITATION"
            if invalid
            else "NO_CITATIONS"
            if not cited
            else "CITED_IDS_PRESENT"
        ),
        # Exact truncation needs finish_reason; reaching requested cap is a proxy.
        "completion_tokens": tokens,
        "generative_quality": "NOT_ASSESSED",
        "legal_effect": "UNKNOWN",
        "supplier_fit": "UNKNOWN",
        "decision": "NOT_DECIDED",
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: local_llm_citation_audit.py RESULTS_JSON")
    records = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps([audit_entry(x) for x in records], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
