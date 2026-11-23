"""Bounded first-party attachment acquisition with private, resumable receipts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from scripts.research.capture_sibur_public_snapshot import NoRedirect
from scripts.research.verify_sibur_public_snapshot import replay_verified_originals

MAX_BYTES = 25 * 1024 * 1024
SUPPORTED = {".docx", ".xlsx", ".pdf"}


def source_refs(snapshot):
    """Only accept links derived from a full first-party SHA-replayed archive."""
    refs = defaultdict(list)
    for group in replay_verified_originals(snapshot):
        for row in group["observations"]:
            for url in row["documentation_urls"]:
                refs[url].append({"external_id": row["external_id"],
                                  "source_sha256": row["source_sha256"],
                                  "source_row": row["source_row"],
                                  "source_url": row["source_url"]})
    return dict(refs)


def valid_url(url):
    value = urlsplit(url)
    return (value.scheme == "https" and value.netloc == "www.sibur.ru"
            and value.path.startswith("/upload/tmp/example/") and not value.query
            and not value.fragment and "%" not in value.path and ".." not in value.path.split("/"))


def fetch(opener, url):
    if not valid_url(url):
        raise ValueError("outside verified origin")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(2):
        try:
            with opener.open(req, timeout=12) as response:
                raw = response.read(MAX_BYTES + 1)
                mime = response.headers.get("Content-Type", "")
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in (502, 503, 504) or attempt:
                raise
        except (TimeoutError, urllib.error.URLError):
            if attempt:
                raise
        time.sleep(2)
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("empty or oversized document")
    return raw, mime


def type_matches(raw, ext):
    if ext == ".pdf":
        return raw.startswith(b"%PDF-")
    if ext in {".docx", ".xlsx"}:
        return raw.startswith(b"PK\x03\x04")
    return False


def acquire(snapshot, output, limit):
    if not 1 <= limit <= 60:
        raise ValueError("invalid bounded batch")
    if output.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("private evidence must stay outside repo")
    output.mkdir(mode=0o700, exist_ok=True)
    refs = source_refs(snapshot)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                         urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    candidates = sorted(refs, key=lambda u: (Path(urlsplit(u).path).suffix.lower() not in SUPPORTED, u))
    count = 0
    for url in candidates:
        ext = Path(urlsplit(url).path).suffix.lower()
        if ext not in SUPPORTED:
            continue
        identity = hashlib.sha256(url.encode()).hexdigest()
        receipt = output / f"{identity}.json"
        if receipt.exists():
            previous = json.loads(receipt.read_text())
            if previous.get("status") == "captured":
                file = output / previous["file"]
                if hashlib.sha256(file.read_bytes()).hexdigest() != previous["sha256"]:
                    raise ValueError("saved document hash mismatch")
            continue
        if count >= limit:
            break
        count += 1
        item = {"url": url, "references": refs[url], "observed_at": datetime.now(UTC).isoformat()}
        try:
            raw, mime = fetch(opener, url)
            if not type_matches(raw, ext):
                raise ValueError("unexpected document signature")
            sha = hashlib.sha256(raw).hexdigest()
            filename = sha + ext
            file = output / filename
            if file.exists():
                if hashlib.sha256(file.read_bytes()).hexdigest() != sha:
                    raise ValueError("existing file hash mismatch")
            else:
                with file.open("xb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            item.update(status="captured", sha256=sha, bytes=len(raw), mime=mime, file=filename)
        except (ValueError, OSError, urllib.error.URLError) as exc:
            item.update(status="review", error=type(exc).__name__)
        temporary = receipt.with_suffix(".partial")
        with temporary.open("x") as stream:
            json.dump(item, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(receipt)
        print(count, item["status"], ext, flush=True)
        time.sleep(0.6)
    return count


def main():
    """Audit an existing bounded first-party archive without downloading or writing."""
    from scripts.research.audit_sibur_saved_documents import audit_saved_documents

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit_saved_documents(args.snapshot, args.output)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if report["status"] != "verified_historical_offline":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
