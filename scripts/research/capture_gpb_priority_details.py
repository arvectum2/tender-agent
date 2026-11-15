"""Capture bounded primary detail snapshots for previously verified GPB candidates."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from src.modules.tender_connectors.etp_gpb.documents import parse_document_entries


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urlsplit(newurl)
        if u.scheme != "https" or u.netloc not in {"etpgpb.ru", "new.etpgpb.ru"} or not u.path.startswith("/procedures/"):
            raise ValueError("outside verified detail scope")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Visible(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = []
        self.tokens = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip.append(tag)

    def handle_endtag(self, tag):
        if self.skip and self.skip[-1] == tag:
            self.skip.pop()

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.tokens.append(" ".join(data.split()))


def inspect(raw, row, final):
    links, unavailable = parse_document_entries(raw, detail_url=final, external_id=row["external_id"])
    p = Visible()
    p.feed(raw.decode("utf8"))
    number = row["number_raw"].removeprefix("№").strip()
    if number not in " ".join(p.tokens):
        raise ValueError("source number not confirmed")
    fields = {}
    for label in ("Номер извещения", "Номер процедуры", "Начальная цена", "Валюта процедуры",
                  "Дата публикации", "Способ закупки", "Текущий статус", "Подача заявок до"):
        if label in p.tokens:
            i = p.tokens.index(label)
            if i + 1 < len(p.tokens):
                fields[label] = p.tokens[i + 1]
    return fields, links, unavailable


def capture(root, row):
    url = row["detail_url"]
    u = urlsplit(url)
    if u.scheme != "https" or u.netloc != "etpgpb.ru":
        raise ValueError("unexpected source")
    op = build_opener(ProxyHandler({}), SafeRedirect(), HTTPSHandler(context=ssl.create_default_context()))
    with op.open(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=12) as response:
        raw = response.read(4_000_001)
        final = response.geturl()
        if response.status != 200 or len(raw) > 4_000_000:
            raise ValueError("unexpected response")
    fields, links, unavailable = inspect(raw, row, final)
    file = root / (row["external_id"].replace(":", "-") + ".html")
    if file.exists():
        if file.is_symlink() or file.read_bytes() != raw:
            raise ValueError("orphan snapshot differs from current source; review required")
    else:
        with file.open("xb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
    time.sleep(0.5)
    return {"external_id": row["external_id"], "source_url": url, "final_url": final,
            "source_sha256": row["source_sha256"], "status": 200,
            "sha256": hashlib.sha256(raw).hexdigest(), "number_present": True, "fields": fields,
            "document_labels": [v["original_filename"] for v in links],
            "published_document_links": links, "unavailable_document_labels": unavailable, "observed_at": datetime.now(UTC).isoformat()}


def select_candidates(rows, priority, seen, limit):
    """Preserve sale observations but do not queue them as procurement demand."""
    pending = [e["observation"] for e in rows
               if e["observation"]["external_id"] in priority - seen]
    sales = [r for r in pending if r["external_id"].startswith("sale:")]
    demand = [r for r in pending if not r["external_id"].startswith("sale:")]
    return demand[:limit], sales


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--stage", choices=["accepting", "completed"], required=True)
    p.add_argument("--limit", type=int, default=20)
    args = p.parse_args()
    if not 1 <= args.limit <= 30:
        raise ValueError("invalid bounded batch")
    os.umask(0o077)
    root = args.root
    output = root / ("active-priority-details" if args.stage == "accepting" else "historical-priority-details")
    output.mkdir(mode=0o700, exist_ok=True)
    manifest = output / "receipts.json"
    existing = json.loads(manifest.read_text()) if manifest.exists() else []
    seen = {r["external_id"] for r in existing if r.get("status") == 200}
    priority = {r["external_id"] for r in json.loads((root / "geh-metadata-priority-history400.json").read_text()) if r["stage"] == args.stage}
    rows = json.loads((root / "geh-verified-db-input-history400.json").read_text())["accepted"]
    review_file = output / "detail-review.json"
    reviews = json.loads(review_file.read_text()) if review_file.exists() else {}
    excluded = {k for k, v in reviews.items() if v["attempts"] >= 3}
    selected, sales = select_candidates(rows, priority, seen | excluded, args.limit)
    if sales:
        print("excluded_sale_observations", len(sales), flush=True)

    def run(row):
        try:
            return capture(output, row)
        except (OSError, ValueError) as exc:
            return {"external_id": row["external_id"], "error": type(exc).__name__, "reason": str(exc)[:200]}

    with ThreadPoolExecutor(max_workers=2) as pool:
        for receipt in pool.map(run, selected):
            if receipt.get("status") != 200:
                key = receipt["external_id"]
                reviews[key] = {**receipt, "attempts": reviews.get(key, {}).get("attempts", 0) + 1}
                tmp_review = review_file.with_suffix(".partial")
                with tmp_review.open("w") as out:
                    json.dump(reviews, out, ensure_ascii=False, indent=2)
                    out.flush()
                    os.fsync(out.fileno())
                tmp_review.replace(review_file)
                print("review", reviews[key], flush=True)
                continue
            existing.append(receipt)
            tmp = manifest.with_suffix(".partial")
            with tmp.open("w") as out:
                json.dump(existing, out, ensure_ascii=False, indent=2)
                out.flush()
                os.fsync(out.fileno())
            tmp.replace(manifest)
            print(receipt["external_id"], receipt["fields"].get("Текущий статус"), len(receipt["published_document_links"]), flush=True)
    print("attempted", len(selected), "total captured", len(existing), flush=True)


if __name__ == "__main__":
    main()
