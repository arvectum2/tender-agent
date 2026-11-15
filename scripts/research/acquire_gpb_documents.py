"""Capture bounded public GPB attachments without opening archives or executing files."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import ssl
import time
import zipfile
from pathlib import Path
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from src.modules.tender_connectors.etp_gpb.documents import parse_document_entries

MAX_BYTES = 25 * 1024 * 1024
OFFICE = {".docx": "word/document.xml", ".xlsx": "xl/workbook.xml"}
SUPPORTED = {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".doc", ".xls", ".rar", ".zip", ".7z"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def valid_bytes(raw, ext):
    if not raw or len(raw) > MAX_BYTES:
        return False
    if ext == ".pdf":
        return raw.startswith(b"%PDF-") and b"%%EOF" in raw[-4096:]
    if ext in OFFICE:
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                infos = z.infolist()
                return (len(infos) < 3000 and sum(i.file_size for i in infos) < 100_000_000
                        and OFFICE[ext] in z.namelist() and not any(i.flag_bits & 1 for i in infos))
        except zipfile.BadZipFile:
            return False
    signatures = {
        ".png": (b"\x89PNG\r\n\x1a\n",), ".jpg": (b"\xff\xd8\xff",),
        ".doc": (bytes.fromhex("d0cf11e0a1b11ae1"),), ".xls": (bytes.fromhex("d0cf11e0a1b11ae1"),),
        ".rar": (b"Rar!\x1a\x07",), ".zip": (b"PK\x03\x04", b"PK\x05\x06"),
        ".7z": (b"7z\xbc\xaf\x27\x1c",),
    }
    return ext in signatures and raw.startswith(signatures[ext])


def references(root):
    rows = []
    for receipt in json.loads((root / "receipts.json").read_text()):
        if receipt.get("status") != 200 or not receipt.get("number_present"):
            continue
        file = root / (receipt["external_id"].replace(":", "-") + ".html")
        raw = file.read_bytes()
        if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError("detail hash mismatch")
        links, _ = parse_document_entries(raw, detail_url=receipt["final_url"],
                                         external_id=receipt["external_id"])
        rows.extend(links)
    return rows


def capture(root, row):
    ext = Path(row["original_filename"]).suffix.lower()
    url = row["document_url"]
    op = build_opener(ProxyHandler({}), NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
    with op.open(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15) as res:
        raw = res.read(MAX_BYTES + 1)
        if res.status != 200 or res.geturl() != url:
            raise ValueError("unexpected source response")
        mime = res.headers.get("Content-Type", "")
    if not valid_bytes(raw, ext):
        raise ValueError("signature, format or size rejected")
    sha = hashlib.sha256(raw).hexdigest()
    name = sha + ext
    file = root / "originals" / name
    if not file.exists():
        with file.open("xb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
    if file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest() != sha:
        raise ValueError("saved original hash mismatch")
    return {**row, "capture_status": "captured", "sha256": sha, "bytes": len(raw),
            "file": name, "mime": mime}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--include-archives", action="store_true")
    p.add_argument("--protocols-only", action="store_true")
    a = p.parse_args()
    if not 1 <= a.limit <= 30:
        raise ValueError("invalid batch")
    os.umask(0o077)
    root = a.root
    (root / "originals").mkdir(mode=0o700, exist_ok=True)
    manifest = root / "document-pilot-receipts.json"
    old = json.loads(manifest.read_text()) if manifest.exists() else []
    seen = {(r["external_id"], r["document_url"]) for r in old}
    refs = references(root)
    allowed = SUPPORTED if a.include_archives else SUPPORTED - {".zip", ".rar", ".7z"}
    tasks = [r for r in refs if (r["external_id"], r["document_url"]) not in seen
             and Path(r["original_filename"]).suffix.lower() in allowed
             and (not a.protocols_only or r.get("document_role") == "published_protocol")][:a.limit]
    for row in tasks:
        try:
            rc = capture(root, row)
        except (OSError, ValueError) as exc:
            rc = {**row, "capture_status": "review", "error": type(exc).__name__,
                  "http_status": getattr(exc, "code", None)}
        old.append(rc)
        tmp = manifest.with_suffix(".partial")
        with tmp.open("w") as f:
            json.dump(old, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(manifest)
        print(row["external_id"], Path(row["original_filename"]).suffix, rc["capture_status"], rc.get("error", ""), flush=True)
        time.sleep(0.4)
    print("attempted", len(tasks), "receipts", len(old), "captured", sum(r["capture_status"] == "captured" for r in old), flush=True)


if __name__ == "__main__":
    main()
