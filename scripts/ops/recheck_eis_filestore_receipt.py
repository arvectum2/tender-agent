"""One EIS filestore attachment recheck against a historic immutable receipt.

Runs a SINGLE authorized read-only HTTPS GET through the standard verified
attachment transport. No automatic retries, storage, TLS bypass, or bids.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from src.modules.tender_operator_agent_demo.attachment_downloader import (
    AttachmentTransportError,
    _default_transport,
)

UID_PATTERN = re.compile(r"[A-Fa-f0-9]{32}\Z")
HASH_PATTERN = re.compile(r"[a-f0-9]{64}\Z")
MAX_BYTES = 30 * 1024 * 1024
MAX_RECEIPT_BYTES = 1024 * 1024


def verify_receipt_entry(row: object) -> tuple[str, int, str]:
    if not isinstance(row, dict):
        raise TypeError("invalid_receipt_entry")
    uid = row.get("uid")
    url = row.get("url")
    signature = row.get("sha256")
    size = row.get("size_bytes")
    if not isinstance(uid, str) or not UID_PATTERN.fullmatch(uid):
        raise ValueError("invalid_official_uid")
    if not isinstance(url, str):
        raise TypeError("invalid_official_url")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "zakupki.gov.ru"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.path != "/44fz/filestore/public/1.0/download/priz/file.html"
        or parsed.fragment
    ):
        raise ValueError("untrusted_official_url")
    qs = parse_qs(parsed.query, keep_blank_values=True)
    if set(qs) != {"uid"} or qs["uid"] != [uid]:
        raise ValueError("mismatched_official_uid")
    if not isinstance(signature, str) or not HASH_PATTERN.fullmatch(signature):
        raise ValueError("invalid_receipt_sha256")
    if type(size) is not int or size < 1 or size > MAX_BYTES:
        raise ValueError("invalid_receipt_size")
    return url, size, signature


def recheck_entry(row: dict, *, transport=_default_transport) -> dict:
    url, expected_bytes, expected_sha = verify_receipt_entry(row)
    try:
        payload, _content_type = transport(url, MAX_BYTES)
    except AttachmentTransportError as exc:
        return {"result": "unavailable", "reason": exc.code,
                "source_binary_verified": False}
    actual_bytes = len(payload)
    if actual_bytes > MAX_BYTES:
        return {"result": "invalid_response", "reason": "file_too_large",
                "source_binary_verified": False}
    sha_equal = hashlib.sha256(payload).hexdigest() == expected_sha
    bytes_equal = actual_bytes == expected_bytes
    return {
        "result": "verified" if sha_equal and bytes_equal else "mismatch",
        "source_binary_verified": sha_equal and bytes_equal,
        "sha256_equal": sha_equal,
        "size_equal": bytes_equal,
        "actual_bytes": actual_bytes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="One read-only official EIS original SHA recheck")
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--index", type=int, required=True,
                        help="Zero-based original binary file index, exactly one.")
    args = parser.parse_args()
    if args.index < 0 or args.receipts.stat().st_size > MAX_RECEIPT_BYTES:
        raise SystemExit("Invalid receipt input")
    records = json.loads(args.receipts.read_text(encoding="utf-8"))
    files = records.get("files")
    if not isinstance(files, list) or args.index >= len(files):
        raise SystemExit("Invalid receipt file index")
    try:
        out = recheck_entry(files[args.index])
    except (TypeError, ValueError) as exc:
        out = {"result": "rejected", "reason": str(exc), "source_binary_verified": False}
    # Never print tokens, signed attachment links or document contents.
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))
    return 0 if out["source_binary_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
