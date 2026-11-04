"""Bounded first-page EIS month searches; never evidence of exhaustive market coverage."""
from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from src.tender_research.providers.public_44fz_search import Public44FzSearchProvider
from src.tender_research.providers.public_223fz_search import Public223FzSearchProvider

SCHEMA = "pq-month-scoped-eis/1"


def _window(month: str) -> tuple[date, date]:
    if not isinstance(month, str) or len(month) != 7 or month[4] != "-":
        raise ValueError("Expected YYYY-MM")
    try:
        year, number = int(month[:4]), int(month[5:])
        start = date(year, number, 1)
        end = date(year, number, calendar.monthrange(year, number)[1])
    except ValueError as exc:
        raise ValueError("Invalid month") from exc
    if not date(2024, 1, 1) <= start <= datetime.now(UTC).date():
        raise ValueError("Outside research period")
    return start, min(end, datetime.now(UTC).date())


def _bound(url: str, law: str, start: date, end: date, query: str) -> bool:
    p = urlsplit(url or "")
    if (p.scheme != "https" or p.hostname != "zakupki.gov.ru"
            or p.username or p.password or p.port not in (None, 443)
            or p.path != "/epz/order/extendedsearch/results.html"):
        return False
    q = parse_qs(p.query)
    return (q.get("publishDateFrom") == [start.strftime("%d.%m.%Y")]
            and q.get("publishDateTo") == [end.strftime("%d.%m.%Y")]
            and q.get("searchString") == [query]
            and q.get("fz223" if law == "223fz" else "fz44") == ["on"]
            and q.get("pageNumber") == ["1"])


def _atomic(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8",
                                     prefix=".month-", delete=False) as stream:
        temp = Path(stream.name)
        json.dump(state, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _query_in_title(query: str, title: str) -> bool:
    """Do not count «остатком/недостатком» as a STATCOM title hit."""
    if query.casefold() == "статком":
        return bool(re.search(r"(?<![\w])статком(?![\w])", title, flags=re.IGNORECASE))
    return query.casefold() in title.casefold()


def run(*, journal: Path, months: list[str], laws: list[str], queries: list[str],
        max_requests: int = 8, retry_hours: int = 12,
        providers: dict | None = None, now: datetime | None = None) -> dict:
    if (not 1 <= max_requests <= 12 or not 1 <= retry_hours <= 720
            or not 1 <= len(months) <= 6 or not 1 <= len(queries) <= 4
            or not laws or any(law not in ("223fz", "44fz") for law in laws)
            or any(not isinstance(q, str) or not q.strip() or len(q) > 100 for q in queries)):
        raise ValueError("Unbounded month discovery")
    windows = [(m, *_window(m)) for m in dict.fromkeys(months)]
    if journal.is_symlink():
        raise ValueError("Unsafe journal")
    state = json.loads(journal.read_text()) if journal.is_file() else {
        "schema_version": SCHEMA, "attempts": []}
    if state.get("schema_version") != SCHEMA or not isinstance(state.get("attempts"), list):
        raise ValueError("Invalid journal schema")
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        raise ValueError("Naive timestamp")
    recent = {}
    for row in state["attempts"]:
        try:
            key = row["law"], row["month"], row["query"]
            stamp = datetime.fromisoformat(row["timestamp"])
            if stamp.tzinfo is None or stamp > current:
                raise ValueError("Bad timestamp")
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError("Malformed journal: fail closed") from exc
        recent[key] = stamp
    sources = providers or {"223fz": Public223FzSearchProvider(),
                            "44fz": Public44FzSearchProvider()}
    events = []
    for month, start, end in windows:
        for law in dict.fromkeys(laws):
            for query in dict.fromkeys(queries):
                if len(events) >= max_requests:
                    break
                key = law, month, query
                if key in recent and (current - recent[key]).total_seconds() < retry_hours * 3600:
                    continue
                try:
                    page = sources[law].search(query=query, date_from=start, date_to=end,
                                               page=1, page_size=30)
                    if not _bound(page.source_url, law, start, end, query):
                        raise ValueError("Official date-bound URL mismatch")
                    candidates = [{"number_unverified": item.registry_number,
                                   "title_unverified": (getattr(item, "title", None) or "")[:300],
                                   "customer_unverified": (getattr(item, "customer_name", None) or "")[:200],
                                   "publication": item.publication_date.isoformat()
                                   if item.publication_date else None,
                                   "query_in_visible_title": _query_in_title(
                                       query, getattr(item, "title", None) or ""),
                                   "pq_relevance_verified": False,
                                   "date_in_window": bool(item.publication_date)
                                   and start <= item.publication_date.date() <= end}
                                  for item in page.items[:30]]
                    result = {"status": str(page.status), "source_url": page.source_url,
                              "date_bounds_verified": True, "candidates": candidates,
                              "first_page_has_next": page.has_next}
                except Exception as exc:  # noqa: BLE001 - bounded external provider failure is journaled
                    result = {"status": "provider_error", "error_type": type(exc).__name__,
                              "date_bounds_verified": False, "candidates": []}
                event = {"timestamp": current.isoformat(), "law": law, "month": month,
                         "query": query, "page": 1, "query_scoped_not_exhaustive": True,
                         "original_documents_verified": False,
                         "signed_contract_verified": False, **result}
                state["attempts"].append(event)
                events.append(event)
                _atomic(journal, state)
            if len(events) >= max_requests:
                break
        if len(events) >= max_requests:
            break
    return {"requests_this_run": len(events), "total_journaled": len(state["attempts"]),
            "date_bound_responses": sum(x["date_bounds_verified"] for x in events),
            "candidate_metadata_rows": sum(len(x["candidates"]) for x in events),
            "coverage_exhaustive": False,
            "statuses": {s: sum(x["status"] == s for x in events)
                         for s in sorted({x["status"] for x in events})}}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--month", action="append", required=True)
    p.add_argument("--law", choices=("223fz", "44fz"), action="append", required=True)
    p.add_argument("--query", action="append", required=True)
    p.add_argument("--max-requests", type=int, default=8)
    a = p.parse_args()
    print(json.dumps(run(journal=a.journal, months=a.month, laws=a.law,
                         queries=a.query, max_requests=a.max_requests), ensure_ascii=False))


if __name__ == "__main__":
    main()
