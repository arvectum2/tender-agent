"""SHA-bound first-party buyer INN for RN61005187; no award inference."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from scripts.market_intelligence.append_pq_delta_20261029 import (
    ROOT,
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.enrich_pq_missing_field import get_row
from scripts.market_intelligence.enrich_pq_primary_gaps_20261101 import apply, validate

CID = "commercial:РН61005187:lot1"
RAW_CASE_ID = "commercial:RN61005187:lot1"  # historical Latin receipt alias
URL = "https://www.tektorg.ru/rosnefttkp/procedures/20083978"
REL = "captures/commercial_RN61005187_lot1/20261030T033746639989Z-7fd0c4aa-ad145e070ebaf2d0.bin"
SHA = "ad145e070ebaf2d085781beddf15a07a46b38ff3a92a141eb0c3b281f44bc037"
INN = "7536125117"
CASE = {"cid": CID, "scope": "supply", "nmck": None,
        "field": "customer.inn", "value": INN}


def proof(root: Path = ROOT) -> dict:
    root = root.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise ValueError("Internal APFS evidence only")
    p = (root / REL).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or not 1000 < p.stat().st_size < 1000000:
        raise ValueError("Unsafe original")
    raw = p.read_bytes()
    receipt = json.loads(Path(str(p) + ".json").read_text())
    if (hashlib.sha256(raw).hexdigest() != SHA
            or receipt.get("sha256") != SHA or receipt.get("case_id") != RAW_CASE_ID
            or receipt.get("source_url") != URL or receipt.get("relative_file") != REL
            or receipt.get("http_status") != 200 or receipt.get("bytes") != len(raw)):
        raise ValueError("SHA/receipt/identity mismatch")
    match = re.search(rb'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                      raw, re.DOTALL)
    if not match:
        raise ValueError("Missing first-party JSON")
    item = json.loads(match[1])["props"]["pageProps"]["procedureItem"]
    if (item.get("id") != 20083978 or item.get("remoteId") != 1198658
            or item.get("registryNumber") != "РН61005187"
            or item.get("inn") != INN
            or "ХАРАМПУРНЕФТЕГАЗ" not in item.get("organizerName", "")
            or "ДФКУ, УКРМ" not in item.get("title", "")
            or item.get("typeName") != "Запрос (Т)КП"):
        raise ValueError("Official buyer/lot identity mismatch")
    return {"url": URL, "sha256": SHA, "source_tier": "first_party_tektorg_card",
            "excerpt": "РН61005187; ДФКУ, УКРМ; ИНН 7536125117"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-manifest", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    source = proof()
    row = get_row(CID)
    if (row["data"].get("customer", {}).get("name") != "ООО «Харампурнефтегаз»"
            or row["data"].get("description") != "Поставка ДФКУ, УКРМ"
            or row["data"].get("publication_date") != "2026-10-23"):
        raise RuntimeError("Buyer/title/date mismatch")
    validate(CASE, row)
    before = snapshot()
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "case": CID, "field": CASE["field"],
                          "value": INN, "source_sha256": SHA, "before": before}, ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError("Fresh backup and exclusive receipt mandatory")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Acceptance gate blocked")
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh full verified backup mandatory")
    result = apply([(CASE, row, source)], before)
    result["new_verified_fields"] = 1
    result["backup_sha256"] = backup["sha256"]
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
