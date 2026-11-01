"""SHA-bound, null-only EIS 223-FZ registered design-contract enrichment.

220 kV substation design contract is not a verified sale of PQ equipment.
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
    "cid": "223fz:32515225588:lot1",
    "inn": None,
    "scope": "design",
    "nmck": "27175270",
    "num": "54716016979250046600000",
    "fields": {
        "contract_registry_number": "54716016979250046600000",
        "contract_number": "07/3-185",
        "contract_signed_date": "2025-11-19",
        "contract_registered_price_rub": "20442391.10",
        "reported_contract_total_rub": "20442391.10",
        "registered_signed_contract_verified": True,
        "buyer_inn": "4716016979",
        "contract_status_note": (
            "ЕИС: договор 07/3-185 от 19.11.2025 на 20 442 391,10 руб. "
            "за проектирование реконструкции СТК на ПС 220 кВ; "
            "не поставка PQ-оборудования. Подписант-поставщик, факт оплаты "
            "и доля оборудования не установлены."
        ),
    },
    "files": [
        (
            "20261101T062959056777Z-1aceaca0-c3fb4aafb7953bbc.bin",
            "c3fb4aafb7953bbcac691b96909663b36a60e6dad8b7a74aafd2b6eb35c9eea5",
            ("https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?"
            "reestrNumber=54716016979250046600000"),
            ["20 442 391,10", "19.11.2025", "ИНН 4716016979"],
        ),
        (
            "20261101T062959427573Z-a56e1810-00dd53019c54cd50.bin",
            "00dd53019c54cd5075a962e6b9de98e7ead3e77c603462a444fb56eb8e2c358e",
            ("https://zakupki.gov.ru/epz/contractfz223/printForm/view.html?"
            "reestrNumber=54716016979250046600000&version=3"),
            ["20 442 391.10", "19.11.2025", "ПИР"],
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
    row = get_row(CASE["cid"])
    before = snapshot()
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
