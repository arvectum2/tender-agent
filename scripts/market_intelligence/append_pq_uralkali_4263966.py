"""Source-bound 10 kV/200 kvar Uralkali supply lead; never a signed sale."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from scripts.market_intelligence.append_b2b_original_card import Visible
from scripts.market_intelligence.append_pq_delta_20261029 import (
    ROOT,
    insert,
    snapshot,
    verified_backup,
)

CID = "commercial:4263966:lot1"
URL = ("https://www.b2b-center.ru/app/market-next/"
       "2744415-ustanovka-reguliruemaia-dlia-kompensatsii-reaktivnoi/tender-4263966/")
ORIGINALS = (
    ("20261102T023828916457Z-4a588a43-dd4d50a4b48b06f6.bin",
     "dd4d50a4b48b06f60b832f9fbe460885bb7bcc024a583dd2c79540767e376b40",
     URL, ("№ 4263966", "N=200кВАр_Uн=10кВ", 'ПАО "УРАЛКАЛИЙ"',
           "Опубликована 12.12.2025", "Итоги подведены 04.02.2026",
           "Решение организатора доступно для авторизованных пользователей")),
    ("20261102T023943699979Z-dab8f333-2ca8246e7792a51d.bin",
     "2ca8246e7792a51d9c754df4aa417b7abda87f8a029744d0b025374aab700993",
     URL + "positions/", ("№ 4263966", "N=200кВАр_Uн=10кВ",
                          "Всего 1 позиция", "без указания максимальной цены", "1 Штука")),
)


def stage(root=ROOT):
    base = root.resolve(strict=True)
    evidence = []
    for name, sha, url, quotes in ORIGINALS:
        rel = "captures/commercial_4263966_lot1/" + name
        p = (base / rel).resolve(strict=True)
        if base not in p.parents or p.is_symlink() or p.stat().st_size > 2_000_000:
            raise ValueError("Unsafe source")
        raw = p.read_bytes()
        receipt = json.loads(Path(str(p) + ".json").read_text())
        if (hashlib.sha256(raw).hexdigest() != sha or receipt.get("sha256") != sha
                or receipt.get("bytes") != len(raw) or receipt.get("source_url") != url
                or receipt.get("case_id") != CID or receipt.get("http_status") != 200
                or receipt.get("relative_file") != rel):
            raise ValueError("Original SHA/receipt/identity mismatch")
        parser = Visible()
        parser.feed(raw.decode("utf8", errors="replace"))
        text = " ".join(" ".join(parser.parts).split())
        if not all(q in text for q in quotes):
            raise ValueError("Missing exact original quote")
        evidence.append({"url": url, "sha256": sha, "source_tier": "first_party_original",
                         "verbatim_quotes": list(quotes)})
    record = {
        "canonical_id": CID, "procedure_id": "4263966", "procurement_regime": "commercial",
        "platform": "B2B-Center", "family": "regulated_reactive_power_compensator",
        "scope": "supply", "market_scope": "core_10kv_equipment_supply_notice",
        "publication_date": "2025-12-12", "customer": {"name": "ПАО «Уралкалий»"},
        "description": "Регулируемая установка компенсации реактивной мощности 200 квар, 10 кВ, 1 шт., Березники",
        "status": "completed_outcome_auth_only", "equipment_voltage_kv": "10",
        "reactive_power_kvar": 200, "quantity": 1, "quantity_unit": "шт",
        "nmck_rub": None, "bid_rub": None, "contract_price_rub": None,
        "equipment_only_price_rub": None, "signed_supplier_verified": False,
        "supplier_verified": False, "paid_verified": False,
        "realized_equipment_revenue_rub": None, "winner": None,
        "contract_signatory": None, "oem": None, "evidence": evidence,
    }
    full = hashlib.sha256(CID.encode()).hexdigest()
    content = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(content).hexdigest()
    meta = {"data_version": "uralkali_first_party_20261102", "procurement_id": CID,
            "procedure_id": "4263966", "regime": "commercial", "family": record["family"],
            "scope": "supply", "market_scope": record["market_scope"], "status": record["status"],
            "source_urls": [e["url"] for e in evidence],
            "source_tiers": [e["source_tier"] for e in evidence],
            "source_original_sha256": [e["sha256"] for e in evidence],
            "research_not_market_population": True, "winning_supplier_only_if_verified": None}
    return {"cid": CID, "id": full[:48], "uri": "urn:arvectum:pq:procurement:" + full,
            "hash": digest, "record": record, "metadata": meta,
            "record_metadata": {"research_version": meta["data_version"],
                                "source_content_hash": digest,
                                "source_evidence_urls": meta["source_urls"]}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    row, before = stage(), snapshot()
    if any(before[k] != 120 for k in ("rows", "unique", "records")):
        raise RuntimeError("Expected 120 unique rows; abort")
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "before": before, "case": CID}))
        return
    if not a.backup_manifest or not a.receipt or a.receipt.exists() or a.receipt.is_symlink():
        raise RuntimeError("Fresh full backup and unused receipt required")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Internal acceptance failed")
    backup = verified_backup(a.backup_manifest)
    if datetime.now(UTC).timestamp() - datetime.fromisoformat(backup["created_at_utc"]).timestamp() > 1800:
        raise RuntimeError("Backup is not fresh")
    result = insert([row], expected=120)
    receipt = {"schema_version": "pq-uralkali-first-party-import/1", "before": before,
               **result, "backup_sha256": backup["sha256"], "new_unique_lots": 1,
               "verified_core_6_35kv_supply_leads": 1,
               "new_signed_suppliers": 0, "new_paid_equipment_sales": 0}
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    a.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
