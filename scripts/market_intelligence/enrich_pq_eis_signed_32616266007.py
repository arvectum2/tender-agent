"""Guarded EIS 32616266007 signed contract enrichment; procedure status preserved."""
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

CID = "223fz:32616266007:lot1"
NUM = "54716016979260041190000"
FIELDS = {
    "contract_registry_number": NUM,
    "contract_number": "1605245",
    "contract_signed_date": "2026-10-14",
    "contract_registered_price_rub": "662460.00",
    "reported_contract_total_rub": "662460.00",
    "registered_signed_contract_verified": True,
    "contract_status_note": (
        "Процедура признана несостоявшейся при одной допущенной заявке из двух; "
        "договор №1605245 на 662 460 руб. заключён 14.10.2026. "
        "Подписант-поставщик и оплата не установлены."
    ),
}
CASE = {
    "cid": CID, "inn": "4716016979", "scope": "capacitor_component_supply_spares",
    "nmck": "856440.00", "num": NUM, "fields": FIELDS,
    "files": [
        (
            "20261031T183613863556Z-44b6572e-08b09706b512f497.bin",
            "08b09706b512f497b94941b5de857d0aabbda3eac9f1df64b4c8bd0d4e8b375c",
            "https://zakupki.gov.ru/epz/contractfz223/printForm/view.html?reestrNumber=" + NUM,
            ["14.10.2026", "662 460.00"],
        ),
        (
            "20261031T173539688444Z-2677dc90-87a2d3a7d45a8d2a.bin",
            "87a2d3a7d45a8d2a0bd06f93dd0c29312b5aa768d011865b3b6fb7b185c1bdab",
            "https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber=" + NUM,
            ["14.10.2026", "662 460,00"],
        ),
    ],
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    sources = proof(CASE)
    row, before = get_row(CID), snapshot()
    validate(CASE, row)
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "before": before, "fields": FIELDS}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Fresh backup and receipt mandatory")
    gate = subprocess.run(
        [sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
        capture_output=True, text=True, check=True, timeout=60,
    )
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Acceptance blocked")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh SHA+pg_restore verified backup required")
    result = apply([(CASE, row, sources)], before)
    result["new_verified_fields"] = len(FIELDS)
    result["backup_sha256"] = backup["sha256"]
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x", encoding="utf8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
