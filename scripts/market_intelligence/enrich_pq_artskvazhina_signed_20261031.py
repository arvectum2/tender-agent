"""Source-SHA-bound null-only registered design contract enrichment, EIS 32616280467.

The 3.68m RUB signed design contract is NOT a PQ hardware supply or paid sale.
"""
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
    proof,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import get_row

CID = "223fz:32616280467:lot1"
REG = "56450925977260018070000"
FIELDS = {
    "contract_registry_number": REG,
    "contract_number": "2640-004569",
    "contract_signed_date": "2026-09-03",
    "contract_registered_price_rub": "3680106.21",
    "registered_signed_contract_verified": True,
    "voltage_kv": "10",
    "commission_first_place_bid_rub": "3680106.21",
    "commission_first_place_application": "1",
    "commission_protocol_number": "32616280467-01",
    "commission_protocol_date": "2026-08-21",
}
CASE = {
    "cid": CID, "inn": "6450925977", "scope": "design",
    "nmck": "3683790.00", "num": REG, "fields": FIELDS,
    "files": [
        (
            "20261031T203943972278Z-dadec426-f5fe8fa61dd8a6f7.bin",
            "f5fe8fa61dd8a6f7ba6ceb9cb00129facd7378ecdd857e83787e477e10fed9a8",
            "https://zakupki.gov.ru/epz/contractfz223/printForm/view.html?reestrNumber=" + REG,
            ["2640-004569", "03.09.2026", "3 680 106.21"],
        ),
        (
            "20261031T203944284981Z-ead02763-c68cda41ff03c59a.bin",
            "c68cda41ff03c59a4f1c9dfd69def07985613abe6fe9923dbf9cd8e1fe06f683",
            "https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber=" + REG,
            ["2640-004569", "03.09.2026", "3 680 106,21"],
        ),
    ],
}
EXTRAS = [
    (
        "20261031T203914386693Z-7d549577-87f948cd4282a6f8.bin",
        "87f948cd4282a6f8e48dbee05e3f1e55cc975b39242fc8a88f2ed713bad7d818",
        "https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber=32616280467",
        ["32616280467", "ВЛ-10 кВ Артскважина"],
    ),
    (
        "20261031T203948157464Z-4e37942e-32b17b6891e29ba6.bin",
        "32b17b6891e29ba60734590f6ff2bbf029c082c8bc75262889da713b92f38554",
        "https://zakupki.gov.ru/epz/order/notice/protocol223/printForm/view.html?protocolGuid=40f5374c-ee1d-4ca4-2ecb-deb30e2f716c&purchaseNoticeNumber=32616280467",
        ["32616280467-01", "21.08.2026", "3 680 106.21", "1 место", "Заключение договора"],
    ),
]


def extra_proof():
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise RuntimeError("Internal APFS only")
    sources = []
    for name, sha, url, quotes in EXTRAS:
        rel = Path("captures") / CID.replace(":", "_") / name
        path = (root / rel).resolve(strict=True)
        if root not in path.parents or path.is_symlink() or path.stat().st_size > 1_000_000:
            raise ValueError("Unsafe original")
        raw = path.read_bytes()
        receipt = json.loads(Path(str(path) + ".json").read_text())
        if (hashlib.sha256(raw).hexdigest() != sha or receipt["sha256"] != sha
                or receipt["source_url"] != url or receipt["case_id"] != CID
                or receipt["relative_file"] != rel.as_posix() or receipt["http_status"] != 200):
            raise ValueError("Source identity or SHA mismatch")
        parser = Text()
        parser.feed(raw.decode("utf8", "replace"))
        text = " ".join(" ".join(parser.parts).replace("\u00a0", " ").split())
        if not all(q in text for q in quotes):
            raise ValueError(f"Verbatim original quote missing: {url}")
        sources.append({"url": url, "sha256": sha, "excerpt": "; ".join(quotes)})
    return sources


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    sources = proof(CASE) + extra_proof()
    row = get_row(CID)
    before = snapshot()
    validate(CASE, row)
    registry = row["data"].get("registry_contract", {})
    if (registry.get("registry_number") != REG
            or registry.get("official_registered_total_rub") != "3680106.21"
            or registry.get("signed_contract_registry_verified") is not True
            or registry.get("supplier_identity_from_registry_verified") is not False):
        raise RuntimeError("Existing registry contract conflict")
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "before": before,
                          "fields": FIELDS, "original_shas": [x["sha256"] for x in sources]},
                         ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Fresh full backup and unique receipt required")
    gate = subprocess.run(
        [sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
        capture_output=True, text=True, check=True, timeout=60,
    )
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Internal acceptance failed")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh pg_restore and SHA verified backup required")
    result = apply([(CASE, row, sources)], before)
    result["new_verified_fields"] = len(FIELDS)
    result["backup_sha256"] = backup["sha256"]
    result["not_hardware_sale"] = True
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x", encoding="utf8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
