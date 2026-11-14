"""SHA-bound null-only BSK rating: Ufimka EPC is not equipment-only revenue."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from scripts.market_intelligence.append_pq_delta_20261029 import (
    COL,
    ROOT,
    js,
    psql,
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

CID = "223fz:32514476448:lot1"
URL = "https://zakupki.gov.ru/epz/contractfz223/printForm/view.html?reestrNumber=50277071467250001900000"
SHA = "e2cda53c6d962d101846d25b4f2d3881b63a4f6c9c21db70b98c9c299e750dbc"
REL = "captures/223fz_32514476448_lot1/20261102T093616266128Z-0ccb7c0a-e2cda53c6d962d10.bin"
QUOTE = "БСК 10 кВ 2х0,9 Мвар"
VALUE = "2×0,9 Мвар"


def proof(root=ROOT):
    root = Path(root).resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise RuntimeError("Internal APFS only")
    p = (root / REL).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or not 32 <= p.stat().st_size <= 12000000:
        raise ValueError("Unsafe original")
    raw, receipt = p.read_bytes(), json.loads(Path(str(p) + ".json").read_text())
    if (hashlib.sha256(raw).hexdigest() != SHA
            or any(receipt.get(k) != v for k, v in {
                "sha256": SHA, "source_url": URL, "case_id": CID,
                "relative_file": REL, "http_status": 200}.items())
            or QUOTE.encode() not in raw):
        raise ValueError("Original SHA/receipt/quote mismatch")
    return {"url": URL, "sha256": SHA, "source_tier": "first_party_eis_signed_contract",
            "excerpt": QUOTE, "scope_note": "mixed EPC; equipment-only price unknown"}


def validate(row):
    d = row["data"]
    if (row["id"] != CID or row["owner"] != "tender-agent"
            or d.get("canonical_id") != CID or d.get("procedure_id") != "32514476448"
            or d.get("scope") != "epc" or d.get("equipment_voltage_kv") != 10
            or d.get("quantity") != 2 or d.get("power") is not None
            or "Уфимка" not in d.get("description", "")
            or digest(d) != row["hash"] or "ufimka_bsk_power_20261102" in row["meta"]):
        raise RuntimeError("Identity/old-null/content CAS conflict")


def prepared(row, evidence):
    data = {**row["data"], "power": VALUE,
            "evidence": [*row["data"].get("evidence", []), evidence]}
    h = digest(data)
    meta = {**row["meta"], "source_content_hash": h,
            "ufimka_bsk_power_20261102": {
                "power": VALUE, "source_url": URL, "source_sha256": SHA,
                "exact_original_quote": QUOTE, "previous_hash": row["hash"],
                "previous_revision": row["rev"], "equipment_only_price_verified": False,
                "signed_supplier_verified": False, "paid_sale_verified": False}}
    return data, meta, h


def apply(row, before, evidence):
    data, meta, new_hash = prepared(row, evidence)
    old_hash, rev = row["hash"], row["rev"]
    sql = f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources,dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['unique']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}')<>{before['records']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{old_hash}'
AND d.revision={rev} AND (d.data->'power') IS NULL)<>1
THEN RAISE EXCEPTION 'Ufimka CAS/owner/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},
revision=revision+1,updated_at=now() FROM dp_resources r
WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{old_hash}'
AND d.revision={rev} AND (d.data->'power') IS NULL;
UPDATE dp_resources SET content_hash='{new_hash}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{old_hash}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{new_hash}'
AND d.revision={rev+1} AND d.data->>'power'='{VALUE}'
AND d.metadata->'ufimka_bsk_power_20261102'->>'source_sha256'='{SHA}')<>1
THEN RAISE EXCEPTION 'Ufimka postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after, actual = snapshot(), get_row(CID)
    if (before != after or actual["hash"] != new_hash or actual["rev"] != rev + 1
            or actual["data"].get("power") != VALUE):
        raise RuntimeError("Postcommit readback mismatch")
    return {"canonical_id": CID, "before": before, "after": after,
            "new_verified_fields": 1, "field": "power", "value": VALUE,
            "source_sha256": SHA, "new_hash": new_hash,
            "equipment_only_price_verified": False, "signed_supplier_verified": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    evidence, row, before = proof(), get_row(CID), snapshot()
    validate(row)
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "before": before, "case_id": CID,
                          "power": VALUE, "source_sha256": SHA}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Fresh full backup and receipt required")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Internal APFS acceptance blocked")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh pg_restore-verified full backup required")
    result = apply(row, before, evidence)
    result["backup_sha256"] = backup["sha256"]
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x", encoding="utf8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
