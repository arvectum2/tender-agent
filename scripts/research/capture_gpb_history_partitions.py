"""Verify monthly GEH deadline partitions without touching the live queue."""
from __future__ import annotations

import argparse
import calendar
import fcntl
import hashlib
import json
import os
import re
import shutil
import ssl
import time
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

from scripts.research.capture_gpb_geh_pages import NoRedirect, page_markers
from scripts.research.import_gpb_geh_snapshots import parse_date
from src.modules.tender_connectors.etp_gpb.parser import parse_list


class Count(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = set()

    def handle_data(self, data):
        m = re.fullmatch(r"([0-9][0-9 ]*) предложен(?:ие|ия|ий)", " ".join(data.split()))
        if m:
            self.values.add(int(m[1].replace(" ", "")))


def bounds(month):
    first = date.fromisoformat(month + "-01")
    return first, first.replace(day=calendar.monthrange(first.year, first.month)[1])


def source_url(month, page):
    first, last = bounds(month)
    return "https://etpgpb.ru/procedures/?" + urlencode({
        "page": page, "per": 20, "procedure[section][0]": "geh_group",
        "procedure[stage][0]": "completed", "sort": "by_relevance",
        "procedure[accepted_from]": first.strftime("%d.%m.%Y"),
        "procedure[accepted_to]": last.strftime("%d.%m.%Y")})


def archive_rows(raw, url):
    rows = parse_list(raw, url)
    for row in rows:
        deadline = row.get("deadline_raw", "")
        if " Дата торгов " in deadline:
            left, right = deadline.split(" Дата торгов ", 1)
            # These are two separately labelled source timestamps, not an inferred date.
            parse_date(left)
            parse_date(right)
            row["deadline_raw_original"] = deadline
            row["deadline_raw"] = left
            row["auction_date_raw"] = right
    return rows


def deadline_calendar_date(value):
    """Source filter days are MSK; Jan 31 and Feb 1 2024 full-day probes verified the boundary."""
    return parse_date(value).astimezone(ZoneInfo("Europe/Moscow")).date()


def inspect(raw, month, page):
    q = Count()
    q.feed(raw.decode())
    if len(q.values) != 1:
        raise ValueError("missing or ambiguous source result count")
    total = q.values.pop()
    if total == 0:
        raise ValueError("zero-result month requires explicit review")
    rows = archive_rows(raw, source_url(month, page))
    first, last = bounds(month)
    if any(not first <= deadline_calendar_date(r["deadline_raw"]) <= last for r in rows):
        raise ValueError("deadline outside requested partition")
    current, exposed = page_markers(raw) if total > 20 else (1, 1)
    if current != page or len(rows) > 20:
        raise ValueError("pagination mismatch")
    return {"reported_total": total, "exposed_pages": exposed,
            "expected_pages": (total+19)//20, "ids": [r["external_id"] for r in rows]}


def atomic(path, obj):
    tmp = path.with_suffix(".partial")
    with tmp.open("w") as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


def capture(folder, month, page):
    url = source_url(month, page)
    receipt = folder / f"p{page:04d}.json"
    if receipt.exists():
        row = json.loads(receipt.read_text())
        raw = (folder / row["file"]).read_bytes()
        if row["url"] != url or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("prior source receipt mismatch")
        if inspect(raw, month, page) != row["scope"]:
            raise ValueError("prior source scope mismatch")
        return row
    with build_opener(ProxyHandler({}), NoRedirect(), HTTPSHandler(context=ssl.create_default_context())).open(
        Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15
    ) as res:
        raw = res.read(4_000_001)
        if res.status != 200 or res.geturl() != url or len(raw) > 4_000_000:
            raise ValueError("unexpected HTTP result")
    sha = hashlib.sha256(raw).hexdigest()
    name = f"p{page:04d}-{sha}.html"
    dest = folder / name
    if not dest.exists():
        with dest.open("xb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
    if dest.is_symlink() or hashlib.sha256(dest.read_bytes()).hexdigest() != sha:
        raise ValueError("raw source mismatch")
    result = {"month": month, "page": page, "url": url, "file": name, "sha256": sha,
              "observed_at": datetime.now(UTC).isoformat(), "scope": inspect(raw, month, page)}
    atomic(receipt, result)
    time.sleep(1)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--months", nargs="+", required=True)
    p.add_argument("--probe-only", action="store_true")
    a = p.parse_args()
    os.umask(0o077)
    if len(a.months) != len(set(a.months)) or len(a.months) > 24:
        raise ValueError("bounded unique month sequence required")
    if any(not date(2024,1,1) <= bounds(m)[0] <= date(2025,11,1) for m in a.months):
        raise ValueError("outside approved archive range")
    a.root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (a.root/"archive.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Archive capture already running")
            return
        state_path = a.root/"state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        for month in a.months:
            if (a.root/"STOP").exists():
                return
            folder = a.root / month
            folder.mkdir(mode=0o700, exist_ok=True)
            try:
                head = capture(folder, month, 1)
                scope = head["scope"]
                expected = scope["expected_pages"]
                state[month] = {"status": "probed", "source_count": scope["reported_total"],
                                "expected_pages": expected, "exposed_pages": scope["exposed_pages"]}
                atomic(state_path, state)
                if a.probe_only:
                    print(month, state[month], flush=True)
                    continue
                if expected > 400 or scope["exposed_pages"] != expected:
                    raise ValueError("month exceeds pagination or count mismatch; split further")
                ids = list(scope["ids"])
                for page in range(2, expected+1):
                    if (a.root/"STOP").exists() or shutil.disk_usage(a.root).free < 15*1024**3:
                        state[month]["status"] = "stopped"
                        atomic(state_path, state)
                        return
                    row = capture(folder, month, page)
                    if row["scope"]["reported_total"] != scope["reported_total"]:
                        raise ValueError("source count changed within partition")
                    ids.extend(row["scope"]["ids"])
                    state[month].update(status="capturing", pages=page, unique_ids=len(set(ids)))
                    atomic(state_path, state)
                complete = len(ids) == len(set(ids)) == scope["reported_total"]
                state[month].update(status="verified_complete" if complete else "review",
                                    pages=expected, rows=len(ids), unique_ids=len(set(ids)))
            except (OSError, ValueError) as e:
                state.setdefault(month, {}).update(status="review", error=type(e).__name__, reason=str(e)[:200],
                                                  http_status=getattr(e, "code", None))
                # Access restrictions, throttling and server-wide failure are not a reason
                # to try every remaining partition. Retain evidence and stop.
                if isinstance(e, HTTPError) and e.code in {401, 402, 403, 429, 503}:
                    state[month]["status"] = "blocked"
                    atomic(state_path, state)
                    print(month, state[month], flush=True)
                    return
            atomic(state_path, state)
            print(month, state[month], flush=True)


if __name__ == "__main__":
    main()
