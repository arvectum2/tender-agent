"""First-party registered contracts; guarded null-only PQ fields, no paid-sales claim."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from lxml import html

from scripts.market_intelligence.append_pq_delta_20261029 import (
    ROOT,
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.enrich_pq_eis_contracts_20261031 import apply, validate
from scripts.market_intelligence.enrich_pq_missing_field import get_row

BASE = "https://zakupki.gov.ru/epz/contractfz223/"
CASES = [
    {"cid": "223fz:32515218366:lot1", "scope": "supply", "nmck": "49900000",
     "inn": "7728589190", "num": "67728589190250000820000",
     "fields": {"contract_registry_number": "67728589190250000820000",
                "contract_number": "2025.265144",
                "contract_signed_date": "2025-11-10",
                "contract_registered_price_rub": "49900000.00",
                "registered_signed_contract_verified": True},
     "files": [
         ("20261101T093620615430Z-ffcb22cd-47e4e8d8ca96c44b.bin",
          "47e4e8d8ca96c44b2de920897bc7102f641083c0099d4bf81afd9e11705d25e4",
          BASE + "card/contract-info.html?reestrNumber=67728589190250000820000",
          ["32515218366", "Номер договора 2025.265144", "Цена договора 49 900 000,00", "ИНН 7728589190"]),
         ("20261101T093656506803Z-2c706997-7188133877537f2f.bin",
          "7188133877537f2f12e25ddc8e9b857763bae47ec6526fdb34bbf3c9f4ad79fe",
          BASE + "printForm/view.html?reestrNumber=67728589190250000820000",
          ["32515218366", "Номер договора: 2025.265144", "Цена договора: 49 900 000.00"])]},
    {"cid": "223fz:32615852898:lot1", "scope": "design", "nmck": "2950502.46",
     "inn": None, "num": "52460069527260006170000",
     "fields": {"contract_registry_number": "52460069527260006170000",
                "contract_number": "14.4200.1746.26",
                "contract_signed_date": "2026-06-15",
                "contract_registered_price_rub": "2787700.00",
                "registered_signed_contract_verified": True,
                "voltage_kv": "10"},
     "files": [
         ("20261101T093620966101Z-a5f9d459-e25677cd34567099.bin",
          "e25677cd34567099993c27dd6762377e2a11cd01096a2dc05e5ee9335a3c51e6",
          BASE + "card/contract-info.html?reestrNumber=52460069527260006170000",
          ["32615852898", "Номер договора 14.4200.1746.26", "Цена договора 2 787 700,00", "ВЛ 10 кВ"]),
         ("20261101T093656922446Z-99c01668-5c7ce3c6adb52c39.bin",
          "5c7ce3c6adb52c39b99c3dd24b71de869a0c7f99f6da4b068246daa152b20747",
          BASE + "printForm/view.html?reestrNumber=52460069527260006170000",
          ["32615852898", "Номер договора: 14.4200.1746.26", "Цена договора: 2 787 700.00", "ВЛ 10 кВ"])]},
]


def proof(c):
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise RuntimeError("Internal APFS required")
    sources = []
    for name, sha, url, quotes in c["files"]:
        rel = Path("captures") / c["cid"].replace(":", "_") / name
        path = (root / rel).resolve(strict=True)
        if root not in path.parents or path.is_symlink() or not 32 <= path.stat().st_size <= 1000000:
            raise ValueError("Unsafe source")
        raw = path.read_bytes()
        receipt = json.loads(Path(str(path) + ".json").read_text())
        if (hashlib.sha256(raw).hexdigest() != sha or receipt.get("sha256") != sha
                or receipt.get("source_url") != url or receipt.get("case_id") != c["cid"]
                or receipt.get("relative_file") != rel.as_posix() or receipt.get("http_status") != 200):
            raise ValueError("Source SHA/receipt mismatch")
        tree = html.fromstring(raw.decode("utf8", "replace"))
        for node in tree.xpath("//script|//style"):
            node.drop_tree()
        txt = " ".join(tree.text_content().replace("\xa0", " ").split())
        if c["num"] not in txt or not all(q in txt for q in quotes):
            raise ValueError("Missing exact source quote: " + c["cid"])
        sources.append({"url": url, "sha256": sha, "excerpt": "; ".join(quotes)})
    return sources


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    args = p.parse_args()
    before = snapshot()
    items = []
    for c in CASES:
        sources = proof(c)
        row = get_row(c["cid"])
        validate(c, row)
        items.append((c, row, sources))
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "before": before, "cases": [c["cid"] for c in CASES],
                          "new_verified_fields": 11}, ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError("Backup/receipt required")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Acceptance failed")
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh verified backup required")
    result = apply(items, before)
    result["new_verified_fields"] = 11
    result["backup_sha256"] = backup["sha256"]
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
