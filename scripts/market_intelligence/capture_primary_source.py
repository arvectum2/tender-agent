"""Bounded, content-addressed first-party PQ source snapshots on stable APFS.

Never overwrites prior evidence or changes PostgreSQL. Each capture has a
SHA-256, receipt, timestamp, and immutable unique path for later review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from scripts.market_intelligence.append_pq_delta_20261029 import ROOT

ALLOWED_HOSTS = frozenset({
    "www.b2b-center.ru", "bidzaar.com", "zakupki.gov.ru",
    "etpgpb.ru", "tender.lot-online.ru", "zakaz.etp-region.ru",
    "www.tektorg.ru", "www.roseltorg.ru",
})
MAX_BYTES = 12_000_000


def source_url(raw: str) -> str:
    u = urlsplit(raw)
    if (u.scheme != "https" or u.hostname not in ALLOWED_HOSTS or
            u.username is not None or u.password is not None or u.fragment):
        raise ValueError("Only allowlisted first-party HTTPS endpoints")
    return raw


def store(root: Path, case_id: str, url: str, content: bytes,
          content_type: str = "", http_status: int = 200) -> dict:
    source_url(url)
    if (not re.fullmatch(r"(223fz|commercial):[^\s/\\]+:lot[1-9][0-9]*", case_id)
            or not isinstance(content, bytes) or not 32 <= len(content) <= MAX_BYTES
            or http_status != 200):
        raise ValueError("Invalid first-party capture identity, status or size")
    root = root.expanduser()
    if root.is_symlink():
        raise ValueError("Source root symlink not allowed")
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve(strict=True)
    # macOS removable volumes can stat/open files but fail on scandir.
    list(root.iterdir())
    case_part = re.sub(r"[^A-Za-z0-9_.-]", "_", case_id)
    folder = root / "captures" / case_part
    folder.mkdir(parents=True, exist_ok=True)
    folder = folder.resolve(strict=True)
    digest = hashlib.sha256(content).hexdigest()
    token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + secrets.token_hex(4)
    filename = token + "-" + digest[:16] + ".bin"
    final = folder / filename
    temp = folder / ("." + filename + ".partial")
    manifest = folder / (filename + ".json")
    if final.exists() or temp.exists() or manifest.exists():
        raise FileExistsError("Refuse capture overwrite")
    try:
        with temp.open("xb") as fh:
            os.chmod(temp, 0o600)
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.rename(temp, final)
        receipt = {
            "schema_version": "pq-primary-immutable-capture/1",
            "case_id": case_id,
            "source_url": url,
            "source_tier": "first_party_byte_original",
            "http_status": 200,
            "content_type": content_type,
            "captured_utc": datetime.now(UTC).isoformat(),
            "relative_file": str(final.relative_to(root)),
            "bytes": len(content),
            "sha256": digest,
            "database_mutated": False,
        }
        temp_manifest = folder / ("." + filename + ".json.partial")
        with temp_manifest.open("x", encoding="utf8") as fh:
            fh.write(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.rename(temp_manifest, manifest)
        fd = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return {"receipt_path": str(manifest), **receipt}
    finally:
        if temp.exists():
            temp.unlink()


def fetch(url: str) -> tuple[bytes, str]:
    source_url(url)
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        current = url
        for _ in range(3):
            with client.stream("GET", current, headers={"Accept": "*/*"}) as r:
                if r.status_code in {301, 302, 303, 307, 308}:
                    dest = r.headers.get("location", "")
                    # Official platforms may return relative Location headers.
                    # Resolve against the current URL, then revalidate the
                    # absolute HTTPS destination against the source allowlist.
                    target = urljoin(current, dest)
                    source_url(target)
                    current = target
                    continue
                r.raise_for_status()
                if r.status_code != 200:
                    raise RuntimeError("Only HTTP 200 captured")
                data = bytearray()
                for chunk in r.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise ValueError("First party source exceeded bounded size")
                return bytes(data), r.headers.get("content-type", "")
    raise RuntimeError("Too many source redirects")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--case-id", required=True)
    p.add_argument("--root", type=Path, default=ROOT)
    args = p.parse_args()
    content, kind = fetch(args.url)
    print(json.dumps(store(args.root, args.case_id, args.url, content, kind),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
