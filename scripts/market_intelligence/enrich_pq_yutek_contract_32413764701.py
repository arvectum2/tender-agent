"""Null-only, SHA-verified EIS YUTEK 10kV UKRM quantity and contract fields."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from scripts.market_intelligence.append_pq_delta_20261029 import (
    ROOT,
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.enrich_pq_eis_contract_32515582393 import Text
from scripts.market_intelligence.enrich_pq_eis_contracts_20261031 import (
    apply,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import get_row

CID = "223fz:32413764701:lot1"
NUM = "58601033125240001550000"
CASE = {
    "cid": CID, "inn": "8601033125", "scope": "equipment_supply_new",
    "nmck": "3415594.16", "num": NUM,
    "fields": {"quantity": 1, "contract_number": "13790-сн/24",
               "contract_signed_date": "2024-08-09",
               "registered_signed_contract_verified": True},
    "files": [
        ("20261031T223939834023Z-c436f0a9-24c041d6d1419f05.bin",
         "24c041d6d1419f0564ce85777c0ff3ad96314f71df7180469dd4c0dfa2bc6f28",
         f"https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber={NUM}",
         ["Дата заключения договора 09.08.2024", "4 077 120,00"]),
        ("20261031T233748647063Z-9638a098-25e688151d2bddfd.bin",
         "25e688151d2bddfdab088354f5ad0b525803a1933c465e63f4438d66f0ad283e",
         f"https://zakupki.gov.ru/epz/contractfz223/card/contract-subject.html?reestrNumber={NUM}",
         ["Поставка УКРМ контейнерного типа", "Штука 4 077 120,00"]),
    ],
}



def proof_yutek():
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise RuntimeError("internal APFS required")
    sources = []
    for i, (name, sha, url, quotes) in enumerate(CASE["files"]):
        rel = Path("captures/223fz_32413764701_lot1") / name
        p = (root / rel).resolve(strict=True)
        if root not in p.parents or p.is_symlink() or not 32 <= p.stat().st_size <= 1_000_000:
            raise RuntimeError("unsafe source")
        raw = p.read_bytes()
        receipt = json.loads(Path(str(p) + ".json").read_text())
        if (hashlib.sha256(raw).hexdigest() != sha or receipt.get("sha256") != sha
                or receipt.get("case_id") != CID or receipt.get("source_url") != url
                or receipt.get("relative_file") != rel.as_posix()
                or receipt.get("http_status") != 200):
            raise RuntimeError("source SHA/receipt mismatch")
        parser = Text()
        parser.feed(raw.decode("utf8", "replace"))
        visible = " ".join(" ".join(parser.parts).replace("\u00a0", " ").split())
        mandatory = [NUM, CASE["fields"]["contract_number"], *quotes]
        if i == 0:
            mandatory.append("Извещение о закупке № 32413764701")
        else:
            mandatory.append("Электродвигатели постоянного тока прочие 1 Штука")
        if not all(q in visible for q in mandatory):
            raise RuntimeError("contract identity/quantity quote mismatch")
        sources.append({"url": url, "sha256": sha, "excerpt": "; ".join(quotes)})
    return sources

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    args = p.parse_args()
    sources = proof_yutek()
    row, before = get_row(CID), snapshot()
    validate(CASE, row)
    if row["data"].get("contract_registry_number") != NUM or row["data"].get(
        "contract_registered_price_rub"
    ) != "4077120.00":
        raise RuntimeError("existing registry identity/price conflict")
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "before": before,
                          "fields": CASE["fields"], "sources": sources}, ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError("fresh backup and receipt mandatory")
    gate = subprocess.run(
        [sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
        capture_output=True, text=True, check=True, timeout=60,
    )
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("acceptance blocked")
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("fresh verified full backup required")
    result = apply([(CASE, row, sources)], before)
    result["new_verified_fields"] = len(CASE["fields"])
    result["new_unique_lots"] = 0
    result["new_signed_suppliers"] = 0
    result["backup_sha256"] = backup["sha256"]
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
