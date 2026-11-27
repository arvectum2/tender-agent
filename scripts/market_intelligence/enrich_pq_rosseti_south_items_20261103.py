"""SHA-bound CAS for six capacitor lines of registered Rosseti South contract."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from scripts.market_intelligence.append_pq_delta_20261029 import (
    COL,
    ROOT,
    js,
    psql,
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.enrich_pq_eis_contract_32515582393 import Text
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

CID = "223fz:32616339168:lot1"
REG = "54716016979260038830000"
FILE = "captures/223fz_32616339168_lot1/20261102T223359828217Z-0dcdaefd-4ddf383bfc50e0a2.bin"
SHA = "4ddf383bfc50e0a2a139c0ef000b86a0bd9647c8306ba45f4417f92cff5773e7"
URL = ("https://zakupki.gov.ru/epz/order/notice/notice223/contract/printForm/"
       "viewXml.html?contractRegistrationNumber=54716016979260038830001")
KEY = "eis_rosseti_south_item_split_20261103"
ITEMS = (
    ("КЭПФ-12-450-2 УХЛ1", "12", 11, "137000.00"),
    ("КЭПФ-12-450-2 УХЛ1", "12", 1, "137000.03"),
    ("КЭПФ-11 55-430-2 УХЛ1", "11.55", 5, "270999.99"),
    ("КЭПФ-11 55-430-2 УХЛ1", "11.55", 1, "271000.04"),
    ("КЭПФ-4.2-510-2УХЛ1", "4.2", 5, "180000.00"),
    ("КЭПФ-4.2-510-2УХЛ1", "4.2", 1, "180000.02"),
)


def make_fields():
    lines = [{"model": m, "nominal_kv": v, "quantity": q, "unit_price_rub": p,
              "line_total_rub": str(Decimal(p) * q)} for m, v, q, p in ITEMS]
    high = sum((Decimal(x["line_total_rub"]) for x in lines
                if Decimal(x["nominal_kv"]) >= 6), Decimal(0))
    low = sum((Decimal(x["line_total_rub"]) for x in lines
               if Decimal(x["nominal_kv"]) < 6), Decimal(0))
    if sum(x["quantity"] for x in lines) != 24 or high != Decimal("3270000.02") or low != Decimal("1080000.02"):
        raise RuntimeError("Item price arithmetic mismatch")
    return {
        "contract_capacitor_item_lines": lines,
        "contract_capacitor_nominal_6plus_kv_rub": str(high),
        "contract_capacitor_nominal_below_6kv_rub": str(low),
        "contract_capacitor_printed_item_sum_rub": str(high + low),
        "contract_capacitor_item_rounding_delta_rub": str(high + low - Decimal("4350000.00")),
    }


FIELDS = make_fields()


def proof():
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise RuntimeError("Internal APFS required")
    p = (root / FILE).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or not 32 <= p.stat().st_size <= 1000000:
        raise RuntimeError("Unsafe source")
    raw = p.read_bytes()
    receipt = json.loads(Path(str(p) + ".json").read_text())
    if (hashlib.sha256(raw).hexdigest() != SHA or receipt.get("sha256") != SHA
            or receipt.get("source_url") != URL or receipt.get("case_id") != CID
            or receipt.get("relative_file") != FILE or receipt.get("http_status") != 200):
        raise RuntimeError("Original SHA/receipt mismatch")
    parser = Text()
    parser.feed(raw.decode("utf8", "replace"))
    t = " ".join(" ".join(parser.parts).replace("\xa0", " ").split())
    quotes = (
        "Номер договора: 312", "Дата заключения договора: 28.09.2026",
        "Извещение о закупке: №32616339168", "Цена договора: 4 350 000.00",
        "Конденсатор КЭПФ-12-450-2 УХЛ1", "11, Штука 137 000.00",
        "1, Штука 137 000.03", "Конденсатор КЭПФ-11 55-430-2 УХЛ1",
        "5, Штука 270 999.99", "1, Штука 271 000.04",
        "Конденсатор КЭПФ-4.2-510-2УХЛ1", "5, Штука 180 000.00",
        "1, Штука 180 000.02", "Российская Федерация",
    )
    missing = [q for q in quotes if q not in t]
    if missing:
        raise RuntimeError("Exact quote mismatch: " + repr(missing))
    return {"url": URL, "sha256": SHA, "excerpt": (
        "Договор №312 от 28.09.2026; 24 конденсатора; шесть строк; 4 350 000.00 ₽")}


def validate(row):
    d = row["data"]
    if (row["id"] != CID or row["owner"] != "tender-agent"
            or d.get("canonical_id") != CID or d.get("procedure_id") != "32616339168"
            or d.get("customer", {}).get("inn") != "4716016979"
            or d.get("contract_registry_number") != REG
            or d.get("contract_number") != "312"
            or d.get("contract_registered_price_rub") != "4350000.00"
            or d.get("quantity") != 24 or d.get("registered_signed_contract_verified") is not True
            or d.get("supplier_verified") is not False
            or d.get("pq_equipment_only_contract_rub") is not None
            or digest(d) != row["hash"]
            or any(d.get(k) is not None for k in FIELDS) or KEY in row["meta"]):
        raise RuntimeError("Identity/old-null/hash CAS conflict")


def prepare(row, source):
    data = {**row["data"], **FIELDS}
    data["evidence"] = [*data.get("evidence", []),
                        {**source, "source_tier": "first_party_eis_registered_contract_itemization"}]
    h = digest(data)
    meta = {**row["meta"], "source_content_hash": h, KEY: {
        "source": source, "fields": FIELDS, "previous_hash": row["hash"],
        "previous_revision": row["rev"], "supplier_verified": False,
        "paid_verified": False, "network_6_35kv_verified": False,
        "caution": "Component voltage is not network voltage; item sums exceed registered price by 0.04 RUB."}}
    return data, meta, h


def apply(row, source, before):
    data, meta, h = prepare(row, source)
    nulls = " AND ".join(f"(d.data->'{k}') IS NULL" for k in FIELDS)
    sql = f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources,dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
 WHERE r.collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
 WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{row['hash']}'
 AND d.revision={row['rev']} AND {nulls})<>1
THEN RAISE EXCEPTION 'PQ CAS/owner/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{row['hash']}' AND d.revision={row['rev']} AND {nulls};
UPDATE dp_resources SET content_hash='{h}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{h}'
AND d.revision={row['rev']+1}
AND d.data->>'contract_capacitor_nominal_6plus_kv_rub'='3270000.02'
AND d.metadata->'{KEY}'->'source'->>'sha256'='{SHA}')<>1
THEN RAISE EXCEPTION 'PQ postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after, actual = snapshot(), get_row(CID)
    if (before != after or actual["hash"] != h or actual["rev"] != row["rev"] + 1
            or any(actual["data"].get(k) != v for k, v in FIELDS.items())):
        raise RuntimeError("Postcommit readback mismatch")
    return {"before": before, "after": after, "case": CID, "new_unique_lots": 0,
            "new_verified_fields": len(FIELDS), "new_hash": h, "source": source}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    source = proof()
    row, before = get_row(CID), snapshot()
    validate(row)
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "before": before, "fields": FIELDS,
                          "source": source}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Fresh backup and receipt mandatory")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Acceptance failed")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh SHA+pg_restore backup required")
    result = apply(row, source, before)
    result["backup_sha256"] = backup["sha256"]
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x", encoding="utf8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
