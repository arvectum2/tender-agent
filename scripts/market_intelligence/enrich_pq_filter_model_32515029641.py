"""CAS-guarded 12 kV / 450 kvar KEPF model rating, NOT a paid equipment sale."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from html import unescape
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

CID = "223fz:32515029641:lot1"
MODEL = "КЭПФ-12-450-2 УХЛ1"
FIELDS = {"equipment_voltage_kv": "12",
          "power": "450 кВАр на конденсатор (номинал модели, не всей установки)"}
INTERNAL = Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live")
SOURCES = (
    ("223fz:32514947144:lot1",
     "captures/223fz_32514947144_lot1/20261031T134020351814Z-295defee-5aee81a7a8dc65d4.bin",
     "5aee81a7a8dc65d4314ba718ab7621293ca3d708448958fd22c1cd5bdeb2f94c",
     "https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=AF7F8E3D08204DB9B1D42925DCD4F503"),
    (CID,
     "captures/223fz_32515029641_lot1/20261031T223556731881Z-ab76eee7-ecda30473b4c6fef.bin",
     "ecda30473b4c6fef92b459ea4b41e12af3f2ac34d997bef118ddc35525408463",
     "https://zakupki.gov.ru/epz/contractfz223/printForm/view.html?reestrNumber=54716016979250033980000"),
)


def model_rating_from_text(text):
    return bool(re.search(
        r"КЭПФ-12-450-2\s*УХЛ1\s*\(или эквивалент\)"
        r".{0,100}Напряжение,\s*кВ\s*-\s*12"
        r".{0,100}Мощность,\s*квар\s*[–-]\s*450",
        " ".join(text.split()), re.IGNORECASE))


def evidence():
    if ROOT.resolve(strict=True) != INTERNAL:
        raise RuntimeError("Only internal APFS originals")
    out = []
    for index, (case, rel, sha, url) in enumerate(SOURCES):
        p = (INTERNAL / rel).resolve(strict=True)
        if INTERNAL not in p.parents or p.is_symlink() or not 32 <= p.stat().st_size <= 2_000_000:
            raise RuntimeError("Unsafe original")
        raw = p.read_bytes()
        receipt = json.loads(Path(str(p) + ".json").read_text(encoding="utf8"))
        if (hashlib.sha256(raw).hexdigest() != sha or receipt.get("sha256") != sha
                or receipt.get("case_id") != case or receipt.get("source_url") != url
                or receipt.get("relative_file") != rel or receipt.get("http_status") != 200):
            raise RuntimeError("Original SHA/receipt/case mismatch")
        if index == 0:
            with zipfile.ZipFile(p) as z:
                xml = " ".join(z.read(n).decode("utf8", "replace")
                               for n in z.namelist() if n.startswith("word/") and n.endswith(".xml"))
            if not model_rating_from_text(unescape(re.sub(r"<[^>]+>", " ", xml))):
                raise RuntimeError("Official model nominal rating missing")
        else:
            text = " ".join(unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf8", "replace"))).split())
            if not all(q in text for q in ("32515029641", MODEL, "3 490 560.00")):
                raise RuntimeError("Official signed registry/model mismatch")
        out.append({"url": url, "sha256": sha,
                    "source_tier": ("official_other_lot_same_model_TZ" if index == 0
                                    else "official_this_lot_contract_model"),
                    "excerpt": MODEL + (" / 12 кВ / 450 квар" if index == 0
                                         else " / 12 единиц, registered contract")})
    return out


def validate(row):
    d = row["data"]
    if (row["id"] != CID or row["owner"] != "tender-agent" or digest(d) != row["hash"]
            or d.get("canonical_id") != CID or d.get("procedure_id") != "32515029641"
            or d.get("scope") != "supply_components" or d.get("quantity") != 12
            or d.get("equipment_model") != MODEL
            or any(d.get(k) is not None for k in FIELDS)
            or row["meta"].get("eis_filter_model_crosscase_20261102")
            or not any(e.get("url") == SOURCES[1][3] and e.get("sha256") == SOURCES[1][2]
                       for e in d.get("evidence", []))):
        raise RuntimeError("Identity, old-null, original or content hash conflict")


def prepared(row, sources):
    data = {**row["data"], **FIELDS}
    data["evidence"] = [*data.get("evidence", []), *sources]
    new_hash = digest(data)
    meta = {**row["meta"], "source_content_hash": new_hash,
            "eis_filter_model_crosscase_20261102": {
                "fields": FIELDS, "sources": sources,
                "reference": "same exact model in other official EIS technical specification",
                "not": ["verified grid voltage", "signed supplier", "paid sale"],
                "previous_hash": row["hash"], "previous_revision": row["rev"]}}
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
AND d.revision={rev} AND (d.data->'equipment_voltage_kv') IS NULL
AND (d.data->'power') IS NULL)<>1
THEN RAISE EXCEPTION 'PQ CAS/owner/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},
revision=revision+1,updated_at=now() FROM dp_resources r
WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{old_hash}'
AND d.revision={rev} AND (d.data->'equipment_voltage_kv') IS NULL
AND (d.data->'power') IS NULL;
UPDATE dp_resources SET content_hash='{new_hash}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{old_hash}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{new_hash}'
AND d.revision={rev+1} AND d.data->>'equipment_voltage_kv'='12'
AND d.metadata->'eis_filter_model_crosscase_20261102'->'sources'->1->>'sha256'='{SOURCES[1][2]}')<>1
THEN RAISE EXCEPTION 'PQ postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after, actual = snapshot(), get_row(CID)
    if (before != after or actual["hash"] != new_hash or actual["rev"] != rev+1
            or any(actual["data"].get(k) != v for k, v in FIELDS.items())):
        raise RuntimeError("Postcommit readback mismatch")
    return {"case_id": CID, "new_verified_model_fields": 2, "fields": FIELDS,
            "before": before, "after": after, "source_shas": [s["sha256"] for s in sources],
            "new_hash": new_hash, "signed_supplier_verified": False, "paid_sale_verified": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    sources, before, row = evidence(), snapshot(), get_row(CID)
    validate(row)
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "case_id": CID, "fields": FIELDS,
                          "before": before, "source_shas": [s["sha256"] for s in sources]},
                         ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Fresh verified backup and receipt required")
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
