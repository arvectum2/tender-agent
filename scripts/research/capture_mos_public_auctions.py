"""Read only public finished auction pages and matched public detail records."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from src.modules.tender_connectors.mos_portal.public_auction import (
    DETAIL,
    LIST,
    detail_row,
    list_row,
    query,
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(root, url, prefix):
    opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json",
                                          "Referer": "https://zakupki.mos.ru/"}), timeout=15) as response:
        raw = response.read(4_000_001)
        if response.status != 200 or response.geturl() != url or len(raw) > 4_000_000:
            raise ValueError("unexpected public response")
    sha = hashlib.sha256(raw).hexdigest()
    name = f"{prefix}-{sha}.json"
    dest = root / name
    if not dest.exists():
        with dest.open("xb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
    if dest.is_symlink() or hashlib.sha256(dest.read_bytes()).hexdigest() != sha:
        raise ValueError("source hash mismatch")
    return json.loads(raw, parse_float=__import__("decimal").Decimal), {
        "url": url, "sha256": sha, "file": name, "status": 200,
        "observed_at": datetime.now(UTC).isoformat()}


def append(path, event):
    with path.open("a") as f:
        json.dump(event, f, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--skip", type=int, default=0)
    p.add_argument("--take", type=int, default=10)
    p.add_argument("--replay-list", type=Path)
    p.add_argument("--replay-receipt", type=Path)
    args = p.parse_args()
    os.umask(0o077)
    root = args.root
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    journal = root / "observations.jsonl"
    done = {r["external_id"] for line in journal.read_text().splitlines() if (r := json.loads(line)).get("verification") == "PUBLIC_AUCTION_LIST_AND_DETAIL"} if journal.exists() else set()
    url = LIST + "?" + urlencode({"queryDto": json.dumps(query(args.skip, args.take), separators=(",", ":"))})
    if args.replay_list and args.replay_receipt:
        receipt = json.loads(args.replay_receipt.read_text())
        raw = args.replay_list.read_bytes()
        if (receipt.get("status") != 200 or receipt.get("url") != url
                or hashlib.sha256(raw).hexdigest() != receipt["sha256"]):
            raise ValueError("list replay provenance mismatch")
        receipt["file"] = "list-" + receipt["sha256"] + ".json"
        dest = root / receipt["file"]
        if not dest.exists():
            with dest.open("xb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
        if hashlib.sha256(dest.read_bytes()).hexdigest() != receipt["sha256"]:
            raise ValueError("stored replay mismatch")
        value = json.loads(raw, parse_float=__import__("decimal").Decimal)
    else:
        try:
            value, receipt = fetch(root, url, "list")
        except HTTPError as exc:
            append(root / "review.jsonl", {"url": url, "http_status": exc.code,
                                         "observed_at": datetime.now(UTC).isoformat()})
            raise
    append(root / "pages.jsonl", {**receipt, "reported_count": value.get("count"), "rows": len(value["items"])})
    if len(value["items"]) > args.take:
        raise ValueError("unexpected list size")
    for raw in value["items"]:
        try:
            listing = list_row(raw)
            ident = listing["external_id"]
            if listing["state"] not in {"finished", "offers_signed"}:
                raise ValueError("unexpected historical status")
            if ident in done:
                continue
            detail, evidence = fetch(root, DETAIL + "?" + urlencode({"auctionId": ident}), "auction-" + ident)
            row = detail_row(detail, listing)
            append(journal, {**row, "list_receipt": receipt, "detail_receipt": evidence})
            print(ident, row["state"], len(row["items"]), row["initial_position_sum_matches"], flush=True)
        except (OSError, ValueError, KeyError, ArithmeticError, TypeError) as exc:
            append(root / "review.jsonl", {"external_id": str(raw.get("auctionId")), "list_receipt": receipt,
                                           "error": type(exc).__name__, "reason": str(exc)[:200]})
            print("review", raw.get("auctionId"), type(exc).__name__, flush=True)
        time.sleep(0.8)


if __name__ == "__main__":
    main()
