"""Source-SHA/CAS enrichment of registered 6 kV UKRM mixed-EPC contract.

The 17m RUB full EPC price is not an equipment-only price or paid sale.
"""
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
from scripts.market_intelligence.enrich_pq_eis_contracts_20261031 import (
    apply,
    proof,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import get_row

CASE = {
    "cid": "223fz:32616120582:lot1",
    "inn": "7802312751",
    "scope": "epc",
    "nmck": "21120361.66",
    "num": "57802312751260008280000",
    "fields": {
        "contract_registry_number": "57802312751260008280000",
        "contract_number": "КАР/00225/26",
        "contract_signed_date": "2026-08-19",
        "contract_registered_price_rub": "17000000.00",
        "reported_contract_total_rub": "17000000.00",
        "registered_signed_contract_verified": True,
        "voltage_kv": "6",
        "contract_status_note": (
            "ЕИС: договор КАР/00225/26 от 19.08.2026 на 17 000 000 руб. "
            "за смешанный EPC: ЛЭП 6 кВ, монтаж УКРМ 6 кВ, учёт 0,4 кВ. "
            "Итоговый протокол 32616120582-04: заявка 4149972340, 1 место, "
            "предложение 17 000 000 руб. Подписант-поставщик, фактическая "
            "оплата и стоимость одной УКРМ отдельно не подтверждены."
        ),
    },
    "files": [
        (
            "20261101T063358334882Z-15f77e86-34d0c247faaea86a.bin",
            "34d0c247faaea86a700c495e6789ac37b4d537658df3781afa3787cbdf3f1af7",
            ("https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?"
            "reestrNumber=57802312751260008280000"),
            ["17 000 000,00", "19.08.2026", "Лот №1"],
        ),
        (
            "20261101T063358720960Z-1b8b19f3-81702e88f5688045.bin",
            "81702e88f56880456f6c0777b2b5514eebae12f30ca7f6386b83c8f4203da88c",
            ("https://zakupki.gov.ru/epz/contractfz223/printForm/view.html?"
            "reestrNumber=57802312751260008280000&version=1"),
            ["17 000 000.00", "19.08.2026", "6 кВ", "УКРМ"],
        ),
    ],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-manifest", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    sources = proof(CASE)
    row, before = get_row(CASE["cid"]), snapshot()
    validate(CASE, row)
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "before": before,
                          "case": CASE["cid"], "fields": list(CASE["fields"]),
                          "source_shas": [s["sha256"] for s in sources]},
                         ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError("Fresh full backup and receipt required")
    gate = subprocess.run(
        [sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
        capture_output=True, text=True, check=True, timeout=60,
    )
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Internal APFS acceptance failed")
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh SHA + pg_restore verified backup required")
    result = apply([(CASE, row, sources)], before)
    result["new_verified_fields"] = len(CASE["fields"])
    result["backup_sha256"] = backup["sha256"]
    result["supplier_verified"] = False
    result["paid_sale_verified"] = False
    result["pq_equipment_only_price_verified"] = False
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
