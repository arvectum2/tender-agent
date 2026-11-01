"""Add one previously absent buyer INN from immutable EIS notice, CAS-only."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from scripts.market_intelligence.append_pq_delta_20261029 import (
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.enrich_pq_missing_field import get_row
from scripts.market_intelligence.enrich_pq_primary_gaps_20261101 import (
    apply,
    validate,
    verify,
)

CASE = {
    "cid": "223fz:32615852898:lot1",
    "scope": "design",
    "nmck": "2950502.46",
    "sha": "e7af1bc268c0e24361e2f1d79eaaa8fafe88f5b7a1eaf24c5c27744654833ce0",
    "rel": "captures/223fz_32615852898_lot1/"
           "20261101T093534370583Z-712a1713-e7af1bc268c0e243.bin",
    "url": "https://zakupki.gov.ru/epz/order/notice/notice223/"
           "common-info.html?regNumber=32615852898",
    "quotes": [
        "32615852898",
        'ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО "РОССЕТИ СИБИРЬ"',
        "ИНН 2460069527 КПП 246001001",
    ],
    "field": "customer.inn",
    "value": "2460069527",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-manifest", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    source = verify(CASE)
    row = get_row(CASE["cid"])
    validate(CASE, row)
    before = snapshot()
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "source": source,
                          "case": CASE["cid"], "before": before}, ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError("Fresh full backup and unique receipt required")
    gate = subprocess.run(
        [sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
        capture_output=True, text=True, check=True, timeout=60,
    )
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Internal APFS acceptance failed")
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh SHA + pg_restore validated backup required")
    result = apply([(CASE, row, source)], before)
    result["new_verified_fields"] = 2  # buyer INN and first-party source URL
    result["backup_sha256"] = backup["sha256"]
    result["source_sha256"] = CASE["sha"]
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
