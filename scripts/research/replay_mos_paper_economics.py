"""Replay immutable public sources; write a private paper-only report, not transactions."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from src.modules.paper_trading.auction_economics import (
    scenario_report,
    verified_bid_trace,
)
from src.modules.tender_connectors.mos_portal.public_auction import DETAIL, LIST


def load(root, evidence, base, query_name):
    u = urlsplit(evidence["url"])
    if (u._replace(query="", fragment="").geturl() != base or u.fragment
            or set(parse_qs(u.query)) != {query_name} or evidence["status"] != 200):
        raise ValueError("source endpoint mismatch")
    sha = evidence["sha256"]
    path = root / evidence["file"]
    if path.parent != root or path.is_symlink():
        raise ValueError("invalid evidence path")
    raw = path.read_bytes()
    if len(raw) > 4_000_000 or hashlib.sha256(raw).hexdigest() != sha or sha not in path.name:
        raise ValueError("evidence integrity mismatch")
    return json.loads(raw, parse_float=Decimal)


def replay(root):
    rows, seen = [], set()
    for line in (root/"observations.jsonl").read_text().splitlines():
        x = json.loads(line)
        ident = x["external_id"]
        if ident in seen:
            raise ValueError("duplicate auction")
        listing = load(root, x["list_receipt"], LIST, "queryDto")
        detail = load(root, x["detail_receipt"], DETAIL, "auctionId")
        if parse_qs(urlsplit(x["detail_receipt"]["url"]).query)["auctionId"] != [ident]:
            raise ValueError("detail URL identity mismatch")
        matched = [v for v in listing["items"] if str(v["auctionId"]) == ident]
        if len(matched) != 1:
            raise ValueError("ambiguous source listing ID")
        trace = verified_bid_trace(matched[0], detail)
        rows.append({"trace": trace, "economics": scenario_report(trace),
                     "list_sha256": x["list_receipt"]["sha256"],
                     "detail_sha256": x["detail_receipt"]["sha256"]})
        seen.add(ident)
    return {"schema": "paper_auction_economics_v1", "sessions": rows,
            "actual_cost_evidence_count": 0, "signed_contract_evidence_count": 0,
            "execution_allowed": False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a=p.parse_args()
    os.umask(0o077)
    report=replay(a.root)
    raw=json.dumps(report, ensure_ascii=False, indent=2).encode()
    if a.output.exists():
        if a.output.read_bytes() != raw:
            raise ValueError("existing report differs")
    else:
        with a.output.open("xb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
    print("report", hashlib.sha256(raw).hexdigest())
    for row in report["sessions"]:
        t=row["trace"]
        print(t["auction_id"],t["bid_count"],t["automatic_bids"],t["reduction_percent"],
              [v["max_supplier_basket_rub"] for v in row["economics"]["scenarios"]])


if __name__=="__main__":
    main()
