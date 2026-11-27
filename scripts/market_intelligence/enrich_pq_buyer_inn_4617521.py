"""Source-bound, null-only buyer INN enrichment for B2B tender 4617521."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
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

CID = "commercial:4617521:lot1"
INN = "2310031475"
URL = ("https://www.b2b-center.ru/app/market-next/"
       "vybor-ispolnitelia-na-postavku-montazh-i-pnr-ustanovok-kompensatsii/tender-4617521/")
REL = "captures/commercial_4617521_lot1/20261029T113645921211Z-5d9a6550-02d956e85a58cd25.bin"
SHA = "02d956e85a58cd254b9e1503a892acc94bddb38849bf20f0b1ca721a679dc50f"
QUOTE = 'Акционерное общество \\"ТАНДЕР\\"","АО \\"ТАНДЕР\\"","2310031475"'

def proof() -> dict:
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise ValueError("internal APFS only")
    p = (root / REL).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or p.stat().st_size > 2_000_000:
        raise ValueError("unsafe original")
    b = p.read_bytes()
    m = json.loads(Path(str(p) + ".json").read_text())
    if (hashlib.sha256(b).hexdigest() != SHA or m.get("sha256") != SHA
            or m.get("source_url") != URL or m.get("case_id") != CID
            or m.get("http_status") != 200 or m.get("bytes") != len(b)
            or QUOTE.encode() not in b or "ТДХ Новотитаровская".encode() not in b
            or not re.fullmatch(r"\d{10}", INN)):
        raise ValueError("original SHA/identity/quote mismatch")
    return {"url": URL, "sha256": SHA, "exact_original_quote": QUOTE}

def validate(row: dict) -> None:
    d = row["data"]
    if (row["id"] != CID or row["owner"] != "tender-agent"
            or d.get("canonical_id") != CID or d.get("procedure_id") != "4617521"
            or d.get("scope") != "mixed_supply_install_pnr"
            or d.get("buyer_inn") is not None
            or digest(d) != row["hash"]
            or not any(e.get("url") == URL and e.get("sha256") == SHA
                       for e in d.get("evidence", []))
            or "buyer_inn_field_enrichment" in row["meta"]):
        raise RuntimeError("identity/source/old-null CAS blocked")

def update(row: dict, before: dict, source: dict) -> dict:
    validate(row)
    d = {**row["data"], "buyer_inn": INN}
    h = digest(d)
    meta = {**row["meta"], "source_content_hash": h,
            "buyer_inn_field_enrichment": {
                "field": "buyer_inn", "value": INN, "source": source,
                "previous_hash": row["hash"], "previous_revision": row["rev"]}}
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
AND r.content_hash='{row['hash']}' AND d.revision={row['rev']}
AND (d.data->'buyer_inn') IS NULL)<>1
THEN RAISE EXCEPTION 'buyer INN CAS/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(d)}, metadata={js(meta)},
revision=revision+1, updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id
AND r.collection_id='{COL}' AND r.external_id='{CID}'
AND r.content_hash='{row['hash']}' AND d.revision={row['rev']}
AND (d.data->'buyer_inn') IS NULL;
UPDATE dp_resources SET content_hash='{h}', updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r
JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}'
AND r.content_hash='{h}' AND d.revision={row['rev'] + 1}
AND d.data->>'buyer_inn'='{INN}'
AND d.metadata->'buyer_inn_field_enrichment'->'source'->>'sha256'='{SHA}')<>1
THEN RAISE EXCEPTION 'buyer INN postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after = snapshot()
    actual = get_row(CID)
    if (before != after or actual["hash"] != h or actual["rev"] != row["rev"] + 1
            or actual["data"].get("buyer_inn") != INN):
        raise RuntimeError("postcommit readback mismatch")
    return {"id": CID, "new_verified_fields": 1, "field": "buyer_inn",
            "value": INN, "before": before, "after": after,
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
        print(json.dumps({"mode": "dry_run", "id": CID, "source": source,
                          "before": before}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("fresh backup and unique receipt required")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("preflight failed")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("fresh pg_restore-checked backup required")
    result = update(row, before, source)
    result["backup_sha256"] = backup["sha256"]
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
