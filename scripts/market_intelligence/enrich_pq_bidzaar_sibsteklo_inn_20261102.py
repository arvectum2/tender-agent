"""Source-bound null-only buyer INN enrichment: Bidzaar 306-644."""
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

CID = "commercial:306-644:lot35"
INN = "5406305355"
KEY = "bidzaar_sibsteklo_buyer_inn_20261102"
PROFILE_URL = "https://bidzaar.com/app/companies/tendery/sibsteklo-001-0212"
PROFILE_REL = ("captures/commercial_306-644_lot35/"
               "20261102T003725866813Z-8382345d-fa39eea182d7a2aa.bin")
PROFILE_SHA = "fa39eea182d7a2aa667e2846f9aad8ef36579fc57146997c16d1a2b498fb7f0a"
TECH_URL = "https://bidzaar.com/api/filestorage/files/download/8042258e-bd58-4efc-9f98-b00db6113f82"
TECH_REL = ("captures/commercial_306-644_lot35/"
            "20261102T003515313471Z-1eb0d36f-28c970162cc7b36c.bin")
TECH_SHA = "28c970162cc7b36cff91df3b64ea4168c5717cc43554aea162440e6d10272516"
PROFILE_QUOTE = "ИНН/КПП: 5406305355/540201001"
LEGAL_NAME = 'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "СИБИРСКОЕ СТЕКЛО"'


def check_identity(profile: bytes, technical: bytes) -> None:
    if (PROFILE_QUOTE.encode() not in profile or LEGAL_NAME.encode() not in profile
            or not technical.startswith(b"PK\x03\x04")):
        raise ValueError("First-party buyer identity mismatch")


def proof() -> dict:
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise ValueError("Internal APFS evidence only")
    originals = []
    for rel, sha, url in ((PROFILE_REL, PROFILE_SHA, PROFILE_URL),
                          (TECH_REL, TECH_SHA, TECH_URL)):
        p = (root / rel).resolve(strict=True)
        if root not in p.parents or p.is_symlink() or not 1000 < p.stat().st_size < 1_000_000:
            raise ValueError("Unsafe original")
        raw = p.read_bytes()
        receipt = json.loads(Path(str(p) + ".json").read_text())
        if (hashlib.sha256(raw).hexdigest() != sha or receipt.get("sha256") != sha
                or receipt.get("case_id") != CID or receipt.get("source_url") != url
                or receipt.get("relative_file") != rel or receipt.get("bytes") != len(raw)
                or receipt.get("http_status") != 200):
            raise ValueError("SHA/receipt/case mismatch")
        originals.append(raw)
    check_identity(*originals)
    return {"url": PROFILE_URL, "sha256": PROFILE_SHA,
            "exact_original_quote": PROFILE_QUOTE,
            "technical_sha256": TECH_SHA, "role": "buyer_not_supplier"}


def validate(row: dict) -> None:
    d = row["data"]
    customer = d.get("customer") or {}
    if (row["id"] != CID or row["owner"] != "tender-agent"
            or d.get("canonical_id") != CID or d.get("procedure_id") != "306-644"
            or d.get("scope") != "epc" or customer.get("name") != "СИБСТЕКЛО"
            or d.get("buyer_inn") is not None or customer.get("inn") is not None
            or digest(d) != row["hash"] or KEY in row["meta"]
            or not any(e.get("url") == TECH_URL and e.get("sha256") == TECH_SHA
                       for e in d.get("evidence", []))):
        raise RuntimeError("Owner/identity/old-null/CAS conflict")


def update(row: dict, before: dict, source: dict) -> dict:
    validate(row)
    d = {**row["data"], "buyer_inn": INN,
         "customer": {**row["data"]["customer"], "inn": INN},
         "evidence": [*row["data"].get("evidence", []),
                      {"url": PROFILE_URL, "sha256": PROFILE_SHA,
                       "source_tier": "first_party_bidzaar_buyer_profile",
                       "excerpt": PROFILE_QUOTE}]}
    h = digest(d)
    meta = {**row["meta"], "source_content_hash": h,
            KEY: {"fields": ["buyer_inn", "customer.inn"], "value": INN,
                  "source": source, "previous_hash": row["hash"],
                  "previous_revision": row["rev"],
                  "signed_supplier_verified": False, "paid_sale_verified": False}}
    old_null = ("((d.data->'buyer_inn') IS NULL OR (d.data->'buyer_inn')='null'::jsonb)"
                " AND ((d.data->'customer'->'inn') IS NULL"
                " OR (d.data->'customer'->'inn')='null'::jsonb)")
    sql = f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources, dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}'
AND r.content_hash='{row['hash']}' AND d.revision={row['rev']} AND {old_null})<>1
THEN RAISE EXCEPTION 'Buyer identity CAS/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(d)}, metadata={js(meta)},
revision=revision+1, updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{row['hash']}'
AND d.revision={row['rev']} AND {old_null};
UPDATE dp_resources SET content_hash='{h}', updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}'
AND r.content_hash='{h}' AND d.revision={row['rev']+1}
AND d.data->>'buyer_inn'='{INN}' AND d.data->'customer'->>'inn'='{INN}'
AND d.metadata->'{KEY}'->'source'->>'sha256'='{PROFILE_SHA}')<>1
THEN RAISE EXCEPTION 'Buyer identity postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after = snapshot()
    actual = get_row(CID)
    if (before != after or actual["hash"] != h or actual["rev"] != row["rev"] + 1
            or actual["data"].get("buyer_inn") != INN
            or actual["data"]["customer"].get("inn") != INN):
        raise RuntimeError("Postcommit hash/readback mismatch")
    return {"id": CID, "before": before, "after": after,
            "new_unique_lots": 0, "new_verified_fields": 2,
            "new_signed_suppliers": 0, "new_paid_sales": 0,
            "source": source, "new_hash": h}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    source = proof()
    before = snapshot()
    row = get_row(CID)
    validate(row)
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "id": CID, "before": before,
                          "source": source}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Fresh verified full backup and unique receipt required")
    gate = subprocess.run([sys.executable, "-m",
                           "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Internal APFS gate failed")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh SHA/pg_restore backup required")
    result = update(row, before, source)
    result["backup_sha256"] = backup["sha256"]
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
