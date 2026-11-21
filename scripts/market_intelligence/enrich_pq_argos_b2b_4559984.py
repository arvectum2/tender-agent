"""Bind verified native B2B original to existing Argos 6.3 kV sounding component.

This is an already-known component of a mixed request for indicative prices;
never a newly awarded or signed PQ equipment contract.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from lxml import html

from scripts.market_intelligence.append_pq_delta_20261029 import (
    COL,
    ROOT,
    js,
    psql,
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest

CID = "commercial:4559984:ukrm-6p3-component"
CAPTURE_CID = "commercial:4559984:lot1"
MODEL = "АУКРМ - 6,3 - 1350 - 450 - 12 УХЛ4"
INTERNAL = Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live")
SOURCES = (
    ("captures/commercial_4559984_lot1/20261102T103559376574Z-156da3f8-b525bfaab92fac20.bin",
     "b525bfaab92fac20c1f571615425c43d379085551d9cfd384d23101c0d9e7d31",
     "https://www.b2b-center.ru/app/market-next/zapros-kommercheskikh-predlozhenii-na-postavku-mtr-dlia-ob-ekta/tender-4559984/"),
    ("captures/commercial_4559984_lot1/20261102T103616391252Z-1bf50e8a-78a3a7add2d73115.bin",
     "78a3a7add2d731154087b2e6185f7b4fc02b97c703a73e5c5693f05de053d373",
     "https://www.b2b-center.ru/app/market-next/zapros-kommercheskikh-predlozhenii-na-postavku-mtr-dlia-ob-ekta/tender-4559984/positions/"),
)


def proof():
    if ROOT.resolve(strict=True) != INTERNAL:
        raise RuntimeError("Internal APFS only")
    out = []
    for index, (rel, sha, url) in enumerate(SOURCES):
        p = (INTERNAL / rel).resolve(strict=True)
        if INTERNAL not in p.parents or p.is_symlink() or not 32 <= p.stat().st_size <= 1_000_000:
            raise RuntimeError("Unsafe first-party original")
        raw = p.read_bytes()
        receipt = json.loads(Path(str(p) + ".json").read_text(encoding="utf8"))
        if (hashlib.sha256(raw).hexdigest() != sha or receipt.get("sha256") != sha
                or receipt.get("case_id") != CAPTURE_CID or receipt.get("source_url") != url
                or receipt.get("relative_file") != rel or receipt.get("http_status") != 200):
            raise RuntimeError("Native B2B source receipt/identity/SHA mismatch")
        text = " ".join(" ".join(html.fromstring(raw).itertext()).split())
        if index == 0:
            if not all(s in text for s in ("4559984", 'ООО "АРГОС-СТРОЙ"',
                                          "в целях определения ориентировочной стоимости",
                                          "Завершена", "Общая сумма закупки Не указана")):
                raise RuntimeError("Native B2B card identity/price status mismatch")
        elif not all(s in text for s in ("4559984", MODEL, "1 Комплект",
                                          "6 позиций без указания максимальной цены")):
            raise RuntimeError("Native B2B 6.3kV model/quantity not present")
        out.append({"url": url, "sha256": sha, "source_tier": "first_party_b2b_native",
                    "excerpt": ("4559984 / ООО АРГОС-СТРОЙ / indicative price request"
                                if index == 0 else MODEL + " / 1 комплект / 6 mixed positions")})
    return out


def get_row():
    s = psql(f"""BEGIN READ ONLY;
SELECT jsonb_build_object('id',r.external_id,'hash',r.content_hash,'rev',d.revision,
'data',d.data,'meta',d.metadata,'owner',c.owner)::text
FROM dp_resources r JOIN dp_records d USING(resource_id)
JOIN dp_collections c ON c.collection_id=r.collection_id
WHERE r.collection_id='{COL}' AND r.external_id='{CID}';COMMIT;""")
    matches = [json.loads(line) for line in s.splitlines() if line.startswith("{")]
    if len(matches) != 1:
        raise RuntimeError("Missing or duplicate canonical component")
    return matches[0]


def validate(row):
    d = row["data"]
    if (row["id"] != CID or row["owner"] != "tender-agent" or digest(d) != row["hash"]
            or d.get("canonical_id") != CID or d.get("procedure_id") != "4559984"
            or d.get("scope") != "mixed_MTR_market_sounding_with_PQ_component"
            or d.get("equipment_model") != "АУКРМ-6,3-1350-450-12 УХЛ4"
            or d.get("quantity") != 1 or d.get("equipment_voltage_kv") != 6.3
            or d.get("customer", {}).get("inn") != "8608063577"
            or d.get("source_urls") is not None or row["meta"].get("argos_b2b_original_20261102")
            or not any("synapsenet.ru/zakupki/b2b/4559984" in e.get("url", "")
                       for e in d.get("evidence", []))):
        raise RuntimeError("Wrong identity, prior source, null-field or content hash")


def prepared(row, sources):
    data = dict(row["data"])
    data["source_urls"] = [{"url": s["url"], "sha": s["sha256"], "tier": "first_party"}
                           for s in sources]
    data["evidence"] = [*data.get("evidence", []), *sources]
    new_hash = digest(data)
    meta = {**row["meta"], "source_content_hash": new_hash,
            "argos_b2b_original_20261102": {
                "field": "source_urls", "sources": sources,
                "capture_identity": CAPTURE_CID, "canonical_component": CID,
                "previous_hash": row["hash"], "previous_revision": row["rev"],
                "signed_supplier_verified": False, "equipment_price_verified": False,
                "reactive_power_from_model_unverified": True}}
    return data, meta, new_hash


def apply(row, before, sources):
    data, meta, new_hash = prepared(row, sources)
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
OR (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{old_hash}'
AND d.revision={rev} AND d.data->>'source_urls' IS NULL)<>1
THEN RAISE EXCEPTION 'Argos source CAS/owner/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},
revision=revision+1,updated_at=now() FROM dp_resources r
WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{old_hash}'
AND d.revision={rev} AND d.data->>'source_urls' IS NULL;
UPDATE dp_resources SET content_hash='{new_hash}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{old_hash}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{new_hash}'
AND d.revision={rev+1} AND d.data->'source_urls'->0->>'sha'='{SOURCES[0][1]}'
AND d.data->'source_urls'->1->>'sha'='{SOURCES[1][1]}'
AND d.metadata->'argos_b2b_original_20261102'->>'capture_identity'='{CAPTURE_CID}')<>1
THEN RAISE EXCEPTION 'Argos postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after, actual = snapshot(), get_row()
    if (before != after or actual["hash"] != new_hash or actual["rev"] != rev + 1
            or actual["data"] != data):
        raise RuntimeError("Postcommit readback mismatch")
    return {"case_id": CID, "new_verified_first_party_fields": 1,
            "new_unique_lots": 0, "before": before, "after": after,
            "source_shas": [s["sha256"] for s in sources], "new_hash": new_hash,
            "signed_supplier_verified": False, "paid_sale_verified": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    sources, before, row = proof(), snapshot(), get_row()
    validate(row)
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "case_id": CID, "before": before,
                          "source_shas": [s["sha256"] for s in sources]}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Fresh full backup and receipt required")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Internal APFS acceptance failed")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if not backup.get("pg_restore_list_verified") or not 0 <= age <= 1800:
        raise RuntimeError("Fresh SHA+pg_restore full backup required")
    result = apply(row, before, sources)
    result["backup_sha256"] = backup["sha256"]
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x", encoding="utf8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
