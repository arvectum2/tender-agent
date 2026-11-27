"""SHA-bound 223-FZ Rosseti South capacitor-component signed-contract fields.

This does not verify a named signed supplier, payment, or a full BSK system.
"""
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
from scripts.market_intelligence.enrich_pq_eis_contracts_20261031 import (
    apply,
    proof,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import get_row

CID = "223fz:32616339168:lot1"
REGISTRY = "54716016979260038830000"
FIELDS = {
    "contract_registry_number": REGISTRY,
    "contract_number": "312",
    "contract_signed_date": "2026-09-28",
    "contract_registered_price_rub": "4350000.00",
    "reported_contract_total_rub": "4350000.00",
    "registered_signed_contract_verified": True,
    "commission_bid_rub": "4350000.00",
    "quantity": 24,
    "quantity_unit": "шт.",
    "reported_contract_date": "2026-09-28",
}
CASE = {
    "cid": CID,
    "inn": "4716016979",
    "scope": "supply_components",
    "nmck": "6807600.00",
    "num": REGISTRY,
    "fields": FIELDS,
    "files": [
        (
            "20261101T102942878926Z-cb610a5d-044eae2ab82dd5c1.bin",
            "044eae2ab82dd5c14bd0ba7e1778df0831507285d335e23e0fc542f51f33b3b5",
            f"https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber={REGISTRY}",
            ["28.09.2026", "4 350 000,00"],
        ),
        (
            "20261101T102943246570Z-620f183d-3f4bad551d09fb62.bin",
            "3f4bad551d09fb628aa33d84deb40cd26a13173568ecadc7801aa054c2d47f04",
            f"https://zakupki.gov.ru/epz/contractfz223/printForm/view.html?reestrNumber={REGISTRY}",
            ["28.09.2026", "4 350 000.00", "КЭПФ-4.2-510-2УХЛ1"],
        ),
    ],
}
PROTOCOL_FILE = "20261101T102943705853Z-31181387-643b9699d25e3a79.bin"
PROTOCOL_SHA = "643b9699d25e3a7907293c233ca6f1d0eb40e6de718acfb662debbb9a65d1f36"
PROTOCOL_URL = (
    "https://zakupki.gov.ru/epz/order/notice/protocol223/printForm/view.html"
    "?protocolGuid=bed5a404-eff1-4181-9004-991e767783a5&purchaseNoticeNumber=32616339168"
)


def check_protocol_text(text: str) -> None:
    """Assert outcome and quote, without attributing anonymous bidder to supplier."""
    normalized = " ".join(text.split()).replace("\u00a0", " ")
    for quote in (
        "32616339168-01", "10.09.2026", "6 807 600.00",
        "4 350 000.00", "5 122 536.00", "1 место", "Заключение договора",
    ):
        if quote not in normalized:
            raise ValueError("Protocol original missing quote: " + quote)


def check_itemized_quantity(text: str) -> None:
    """Six distinct item rows: 11+1+5+1+5+1 = 24 capacitor units."""
    normalized = " ".join(text.split()).replace("\u00a0", " ")
    amounts = [int(x) for x in re.findall(r"(?<!\d)(\d+), Штука \d", normalized)]
    if amounts != [11, 1, 5, 1, 5, 1] or sum(amounts) != 24:
        raise ValueError("Itemized contract quantity is not 24")


def verify_protocol() -> dict:
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise RuntimeError("Internal APFS only")
    relative = Path("captures") / "223fz_32616339168_lot1" / PROTOCOL_FILE
    source = (root / relative).resolve(strict=True)
    if root not in source.parents or source.is_symlink() or source.stat().st_size > 1000000:
        raise ValueError("Unsafe protocol original")
    raw = source.read_bytes()
    receipt = json.loads(Path(str(source) + ".json").read_text())
    if (
        hashlib.sha256(raw).hexdigest() != PROTOCOL_SHA
        or receipt.get("sha256") != PROTOCOL_SHA
        or receipt.get("source_url") != PROTOCOL_URL
        or receipt.get("case_id") != CID
        or receipt.get("relative_file") != relative.as_posix()
        or receipt.get("http_status") != 200
        or receipt.get("bytes") != len(raw)
    ):
        raise ValueError("Protocol SHA/receipt drift")
    from scripts.market_intelligence.enrich_pq_eis_contract_32515582393 import Text
    parser = Text()
    parser.feed(raw.decode("utf-8", "replace"))
    check_protocol_text(" ".join(parser.parts))
    return {"url": PROTOCOL_URL, "sha256": PROTOCOL_SHA,
            "excerpt": "Итоговый протокол 10.09.2026; заявка №2 — 4 350 000 руб.; юридическое лицо не раскрыто"}


def validate_lot(row: dict) -> None:
    validate(CASE, row)
    d = row["data"]
    if (
        d.get("supplier_verified") is not False
        or d.get("equipment_voltage_kv") is not None
        or d.get("pq_equipment_only_contract_rub") is not None
        or d.get("quantity") is not None
    ):
        raise RuntimeError("Scope/quantity/supplier old-null conflict")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    args = p.parse_args()
    sources = proof(CASE)
    root = ROOT.resolve(strict=True)
    from scripts.market_intelligence.enrich_pq_eis_contract_32515582393 import Text
    item_source = root / "captures" / "223fz_32616339168_lot1" / CASE["files"][1][0]
    parser = Text()
    parser.feed(item_source.read_text(encoding="utf-8", errors="replace"))
    check_itemized_quantity(" ".join(parser.parts))
    sources.append(verify_protocol())
    before = snapshot()
    row = get_row(CID)
    validate_lot(row)
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "before": before, "case": CID,
                          "fields": FIELDS, "sources": sources}, ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError("Fresh backup and new receipt required")
    gate = subprocess.run(
        [sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
        capture_output=True, text=True, check=True, timeout=60,
    )
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Internal APFS acceptance blocked")
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("New full SHA+pg_restore backup required")
    result = apply([(CASE, row, sources)], before)
    result["new_verified_fields"] = len(FIELDS)
    result["backup_sha256"] = backup["sha256"]
    result["signed_supplier_verified"] = False
    result["paid_sale_verified"] = False
    result["equipment_only_6_35kv_allocation_verified"] = False
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
