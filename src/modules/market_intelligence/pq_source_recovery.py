"""Bounded live EIS lookup for missing PQ procurement evidence.

Uses Tender Agent's verified-TLS official provider, with append-only attempt
receipts. The Data Platform acquisition/extraction boundary is intentionally
separate: a search result is never an original document or a verified award.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from src.tender_research.providers.public_223fz_search import Public223FzSearchProvider
from src.tender_research.providers.public_44fz_search import Public44FzSearchProvider


def _atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8",
                                     prefix=".attempt-", delete=False) as f:
        temp = Path(f.name)
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def run(*, gaps: Path, journal: Path, max_cases: int = 8,
        max_attempts_per_case: int = 2, retry_hours: int = 6) -> dict:
    if not 1 <= max_cases <= 50 or not 1 <= max_attempts_per_case <= 4:
        raise ValueError("Invalid bounded search budget")
    cases = json.loads(gaps.read_text(encoding="utf-8"))["cases"]
    previous = json.loads(journal.read_text(encoding="utf-8")) if journal.exists() else {
        "schema_version": "pq-source-attempts/1", "attempts": []}
    attempted = []
    provider223 = Public223FzSearchProvider()
    provider44 = Public44FzSearchProvider()
    now = datetime.now(timezone.utc)
    for case in cases:
        if len(attempted) >= max_cases:
            break
        number = str(case["procedure_id"])
        if not number.isdigit() or len(number) not in (11, 19, 20):
            continue
        last = [r for r in previous["attempts"] if r["procedure_id"] == number]
        if last:
            elapsed = (now - datetime.fromisoformat(last[-1]["timestamp"])).total_seconds()
            if elapsed < retry_hours * 3600:
                continue
        law = "223fz" if len(number) == 11 else "44fz"
        provider = provider223 if law == "223fz" else provider44
        for query in [number][:max_attempts_per_case]:
            try:
                page = provider.search(query=query, page_size=10)
                matches = [x for x in page.items if x.registry_number == number]
                result = {"status": page.status, "matches": [
                    {"registry_number": x.registry_number, "card_url": x.card_url}
                    for x in matches[:5]], "error": str(page.error)[:300] if page.error else None}
            except Exception as exc:
                result = {"status": "exception", "matches": [], "error_type": type(exc).__name__}
            record = {"timestamp": now.isoformat(), "procedure_id": number,
                      "law": law, "query": query, "source": "official_eis_search",
                      **result, "documents_verified": False,
                      "award_verified": False, "contract_verified": False}
            previous["attempts"].append(record)
            attempted.append(record)
            _atomic(journal, previous)
    return {"attempts_this_run": len(attempted), "total_attempts": len(previous["attempts"]),
            "matched": sum(bool(r["matches"]) for r in attempted),
            "statuses": {s: sum(r["status"] == s for r in attempted)
                         for s in sorted({r["status"] for r in attempted})}}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gaps", type=Path, required=True)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--max-cases", type=int, default=8)
    a = p.parse_args()
    print(json.dumps(run(gaps=a.gaps, journal=a.journal,
                         max_cases=a.max_cases), ensure_ascii=False))


if __name__ == "__main__":
    main()
