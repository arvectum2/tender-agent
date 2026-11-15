"""Resumable public archive capture; one request stream, private immutable receipts."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import ssl
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from scripts.research.capture_sibur_public_snapshot import NoRedirect
from src.modules.tender_connectors.sibur.archive_parser import (
    CATEGORIES,
    archive_page,
    archive_url,
)


def atomic(path, value):
    tmp = path.with_suffix(".partial")
    with tmp.open("w") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def capture(root, category, page):
    folder = root/category
    folder.mkdir(mode=0o700, exist_ok=True)
    receipt_path = folder/f"p{page:05d}.json"
    url = archive_url(category, page)
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        raw = (folder/receipt["file"]).read_bytes()
    else:
        seed = root.parent/f"category-{category}.receipt.json"
        if page == 1 and seed.exists():
            old = json.loads(seed.read_text())
            raw = (root.parent/old["file"]).read_bytes()
            if old["url"] != url or hashlib.sha256(raw).hexdigest() != old["sha256"]:
                raise ValueError("first page seed mismatch")
            observed_at = old["observed_at"]
        else:
            op = build_opener(ProxyHandler({}), NoRedirect(),
                              HTTPSHandler(context=ssl.create_default_context()))
            with op.open(Request(url, headers={"User-Agent": "Mozilla/5.0",
                         "X-Requested-With": "XMLHttpRequest"}), timeout=15) as response:
                raw = response.read(4_000_001)
                if response.status != 200 or response.geturl() != url or len(raw) > 4_000_000:
                    raise ValueError("unexpected archive response")
            observed_at = datetime.now(UTC).isoformat()
            time.sleep(1.4)
        sha = hashlib.sha256(raw).hexdigest()
        name = f"p{page:05d}-{sha}.raw.json"
        dest = folder/name
        if not dest.exists():
            with dest.open("xb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
        if dest.is_symlink() or hashlib.sha256(dest.read_bytes()).hexdigest() != sha:
            raise ValueError("archive original mismatch")
        value = archive_page(raw, category, page)
        receipt = {"category": category, "page": page, "url": url, "file": name,
                   "sha256": sha, "observed_at": observed_at, "rows": len(value.records),
                   "last_page": value.last_page, "ids": [r["external_id"] for r in value.records]}
        atomic(receipt_path, receipt)
    value = archive_page(raw, category, page)
    if (receipt["url"] != url or receipt["sha256"] != value.sha256
            or receipt["last_page"] != value.last_page or receipt["rows"] != len(value.records)
            or receipt["ids"] != [r["external_id"] for r in value.records]):
        raise ValueError("archive receipt mismatch")
    return receipt, value


def collect(root, categories):
    path = root/"state.json"
    state = json.loads(path.read_text()) if path.exists() else {}
    for category in categories:
        if (root/"STOP").exists():
            return
        old = state.get(category, {})
        if old.get("status") in {"review", "blocked"}:
            continue
        try:
            ids = set()
            head, _ = capture(root, category, 1)
            last = head["last_page"]
            observed = 0
            changed = False
            for page in range(1, last+1):
                if (root/"STOP").exists() or shutil.disk_usage(root).free < 15*1024**3:
                    state.setdefault(category, {})["status"] = "stopped"
                    atomic(path,state)
                    return
                receipt, rows = capture(root, category, page)
                changed |= receipt["last_page"] != last
                observed += len(rows.records)
                ids.update(receipt["ids"])
                state[category] = {"status": "capturing", "pages": page,
                                   "initial_advertised_pages": last, "last_advertised_pages": receipt["last_page"],
                                   "rows": observed, "unique_ids": len(ids),
                                   "repeated_rows": observed-len(ids), "page_count_changed": changed,
                                   "updated_at": datetime.now(UTC).isoformat()}
                atomic(path,state)
                if page % 25 == 0:
                    print(category, page, last, observed, flush=True)
            state[category]["status"] = "traversed_with_review" if changed or observed != len(ids) else "advertised_pages_traversed"
            atomic(path,state)
        except (OSError, ValueError) as exc:
            state.setdefault(category, {}).update(status="review", error=type(exc).__name__,
                                                 reason=str(exc)[:180], http_status=getattr(exc,"code",None))
            if isinstance(exc, HTTPError) and exc.code in {401,402,403,429,503}:
                state[category]["status"] = "blocked"
                atomic(path,state)
                return
            atomic(path,state)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--categories",nargs="+",choices=list(CATEGORIES),required=True)
    a=p.parse_args()
    os.umask(0o077)
    if len(a.categories)!=len(set(a.categories)) or a.root.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("unique categories and private runtime required")
    a.root.mkdir(mode=0o700,parents=True,exist_ok=True)
    with (a.root/"archive.lock").open("a") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print("SIBUR archive capture already running")
            return
        collect(a.root,a.categories)


if __name__=="__main__":
    main()
