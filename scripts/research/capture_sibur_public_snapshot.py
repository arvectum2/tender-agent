"""Bounded, private-output research probe; not a production DP transport."""
from __future__ import annotations

import argparse
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from src.modules.tender_connectors.sibur.parser import (
    MAX_RESPONSE,
    page_url,
    parse_page,
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def collect(root: Path, max_pages: int) -> dict:
    if not 1 <= max_pages <= 40:
        raise ValueError("max_pages out of bounds")
    repo = Path(__file__).resolve().parents[2]
    if root.resolve().is_relative_to(repo):
        raise ValueError("private snapshots must be outside repository")
    root.mkdir(mode=0o700)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )

    def write(name, raw):
        with (root / name).open("xb") as f:
            f.write(raw)

    pages, errors = [], []
    grouped = defaultdict(list)
    announced = None

    for n in range(1, max_pages + 1):
        if announced is not None and n > announced:
            break
        try:
            request = urllib.request.Request(
                page_url(n), headers={"X-Requested-With": "XMLHttpRequest", "User-Agent": "Mozilla/5.0"},
            )
            for attempt in range(2):
                try:
                    with opener.open(request, timeout=8) as response:
                        raw = response.read(MAX_RESPONSE + 1)
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code not in (502, 503, 504) or attempt:
                        raise
                except (TimeoutError, urllib.error.URLError):
                    if attempt:
                        raise
                time.sleep(2)
            if len(raw) > MAX_RESPONSE:
                raise ValueError("oversize response")
            write(f"page-{n:03d}.json", raw)
            page = parse_page(raw, n)
            if announced is None:
                announced = page.last_page
            pages.append({
                "page": n, "last_page": page.last_page, "bytes": len(raw), "sha256": page.sha256,
                "rows": len(page.records), "observed_at": datetime.now(UTC).isoformat(),
            })
            for row in page.records:
                grouped[row["external_id"]].append(row)
            print(f"page={n}/{announced} rows={len(page.records)}", flush=True)
        except (ValueError, OSError, urllib.error.URLError) as exc:
            errors.append({"page": n, "error": type(exc).__name__})
            print(f"STOP page={n} {type(exc).__name__}", flush=True)
            break
        time.sleep(0.7)

    metadata = {"source_url", "source_sha256", "source_row"}
    repeated = []
    for identity, observations in grouped.items():
        if len(observations) > 1:
            varying = sorted(k for k in observations[0] if k not in metadata
                             and len({json.dumps(row[k], ensure_ascii=False, sort_keys=True) for row in observations}) > 1)
            repeated.append({"external_id": identity, "observations": len(observations),
                             "varying_fields": varying})
    stable = announced is not None and all(p["last_page"] == announced for p in pages)
    result = {
        "source": "sibur_public", "announced_pages": announced, "validated_pages": len(pages),
        "raw_rows": sum(p["rows"] for p in pages), "unique_ids": len(grouped),
        "repeated_ids": len(repeated), "repeated": repeated, "errors": errors,
        "page_count_stable": stable, "advertised_pages_traversed": stable and len(pages) == announced,
        "verification": "PUBLIC_LIST_SNAPSHOT_NOT_HISTORICAL_COVERAGE", "pages": pages,
    }
    records = [{"external_id": k, "observations": v} for k, v in grouped.items()]
    for name, obj in (("receipts.json", result), ("normalized.json", records)):
        write(name, json.dumps(obj, ensure_ascii=False, indent=2).encode())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-pages", type=int, default=40)
    args = parser.parse_args()
    os.umask(0o077)
    result = collect(args.output, args.max_pages)
    print("SUMMARY", json.dumps({k: v for k, v in result.items()
                                if k not in ("repeated", "pages")}, ensure_ascii=False), flush=True)
    return 0 if result["advertised_pages_traversed"] and not result["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
