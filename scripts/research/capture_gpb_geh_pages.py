"""Resume bounded first-party GEH group list discovery from saved page receipts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from scripts.research.import_gpb_geh_snapshots import stage_for
from src.modules.tender_connectors.etp_gpb.parser import parse_list

MAX_BYTES = 4_000_000
PAGINATOR = re.compile(r'<ul class="paginationSwitcher[^"]*"[^>]*>(.*?)</ul>', re.DOTALL)
CURRENT = re.compile(r'<li class="active paginationSwitcher__item"[^>]*>\s*<span[^>]*>\s*(\d+)\s*</span>')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def page_markers(raw):
    html = raw.decode("utf-8")
    block = PAGINATOR.search(html)
    current = CURRENT.search(html)
    if not block or not current:
        raise ValueError("pagination markers missing")
    numbers = [int(v) for v in re.findall(r">\s*(\d+)\s*</span>", block[1])]
    if not numbers or int(current[1]) not in numbers:
        raise ValueError("invalid paginator")
    return int(current[1]), max(numbers)


def page_url(base, page):
    u = urlsplit(base)
    stage_for(base)
    params = dict(parse_qsl(u.query))
    if params.get("per") != "20" or not 1 <= page <= 1000:
        raise ValueError("invalid page or batch size")
    params["page"] = str(page)
    return urlunsplit((u.scheme, u.netloc, u.path, urlencode(params), ""))


def capture(root, base, page, prefix):
    url = page_url(base, page)
    opener = build_opener(ProxyHandler({}), NoRedirect(),
                         HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15) as res:
        raw = res.read(MAX_BYTES + 1)
        if res.status != 200 or res.geturl() != url:
            raise ValueError("unexpected HTTP result")
    if len(raw) > MAX_BYTES:
        raise ValueError("oversize source")
    current, last = page_markers(raw)
    if current != page:
        raise ValueError("unexpected source page")
    rows = parse_list(raw, url)
    name = f"{prefix}_p{page}"
    target = root / (name + ".html")
    with target.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    time.sleep(0.5)
    return {"name": name, "url": url, "status": 200,
            "sha256": hashlib.sha256(raw).hexdigest(), "rows": len(rows),
            "ids": [r["external_id"] for r in rows],
            "advertised_last_page": last, "current_page": current,
            "observed_at": datetime.now(UTC).isoformat()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--stage", choices=["accepting", "completed"], required=True)
    p.add_argument("--start", required=True, type=int)
    p.add_argument("--end", required=True, type=int)
    a = p.parse_args()
    os.umask(0o077)
    if not 1 <= a.end - a.start + 1 <= 20:
        raise ValueError("invalid bounded range")
    manifest = a.output / "gpb-geh-section-receipts.json"
    existing = json.loads(manifest.read_text())
    base = next(r for r in existing if stage_for(r["url"]) == a.stage)
    if hashlib.sha256((a.output / (base["name"] + ".html")).read_bytes()).hexdigest() != base["sha256"]:
        raise ValueError("base receipt mismatch")
    _, last = page_markers((a.output / (base["name"] + ".html")).read_bytes())
    prefix = "geh_active" if a.stage == "accepting" else "geh_hist"
    tasks = [n for n in range(a.start, min(a.end, last) + 1)
             if f"{prefix}_p{n}" not in {r["name"] for r in existing}]
    def run(n):
        try:
            return capture(a.output, base["url"], n, prefix)
        except (OSError, ValueError) as exc:
            return {"page": n, "error": type(exc).__name__}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for r in pool.map(run, tasks):
            if "error" not in r:
                existing.append(r)
                temp = manifest.with_suffix(".partial")
                with temp.open("w") as stream:
                    json.dump(existing, stream, ensure_ascii=False, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                temp.replace(manifest)
                print(r["name"], r["rows"], r["advertised_last_page"], flush=True)
            else:
                print("review", r, flush=True)
    print("attempted", len(tasks), flush=True)


if __name__ == "__main__":
    main()
