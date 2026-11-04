"""Source-SHA/CAS guarded 6.3kV visual-DOC Bidzaar enrichment."""
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

CID = "commercial:351-062:lot1"
CARD_URL = "https://bidzaar.com/app/process/light/019f415c-8a7a-7c91-bb3f-68da7b9413ea"
DOC_URL = ("https://bidzaar.com/api/filestorage/files/download/"
           "19864dc9-085e-4bbc-a104-bd8205dffe45/"
           "%D0%9E%D0%9B%20%D0%A3%D0%9A%D0%A0%D0%9C%206%20%D0%BA%D0%92.doc")
CARD_REL = "captures/commercial_351-062_lot1/20261031T143251617646Z-b428ec83-097d69a3e4aaff20.bin"
DOC_REL = "captures/commercial_351-062_lot1/20261031T143542412287Z-40651843-e7927732264deb30.bin"
VISUAL_REL = "visual-review-20261101-0039/top.jpg"
CARD_SHA = "097d69a3e4aaff20b38fbe6c5e1ef83263fc2ab567b9004ceb869e7ff2e27894"
DOC_SHA = "e7927732264deb30813bcf967740763cfb032f5710ca78156f76646f8cc0d831"
VISUAL_SHA = "806b5d75e35c9b3bfa694a3dfcbfec2c8eaf44b56fa626fda84671f2e7ed0753"
VALUE = "6.3"
INTERNAL = Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live")


def verified_original():
    if ROOT.resolve(strict=True) != INTERNAL:
        raise RuntimeError("Internal APFS required")
    for rel, sha, url in ((CARD_REL, CARD_SHA, CARD_URL), (DOC_REL, DOC_SHA, DOC_URL)):
        p = (INTERNAL / rel).resolve(strict=True)
        if INTERNAL not in p.parents or p.is_symlink() or p.stat().st_size > 2_000_000:
            raise RuntimeError("Unsafe original")
        receipt = json.loads(Path(str(p) + ".json").read_text())
        if (hashlib.sha256(p.read_bytes()).hexdigest() != sha
                or receipt.get("sha256") != sha or receipt.get("source_url") != url
                or receipt.get("case_id") != CID or receipt.get("http_status") != 200
                or receipt.get("relative_file") != rel):
            raise RuntimeError("First-party original/receipt mismatch")
    card = (INTERNAL / CARD_REL).read_text(encoding="utf-8")
    if (CARD_URL.rsplit("/", 1)[-1] not in card
            or "19864dc9-085e-4bbc-a104-bd8205dffe45" not in card):
        raise RuntimeError("Bidzaar card not linked to DOC")
    visual = (INTERNAL / VISUAL_REL).resolve(strict=True)
    if (INTERNAL not in visual.parents or visual.is_symlink()
            or hashlib.sha256(visual.read_bytes()).hexdigest() != VISUAL_SHA):
        raise RuntimeError("Visual-review derivative SHA mismatch")
    # Human visual inspection of the original DOC table: 'ДА' in 6,3 kV cell.
    # A flattened text extraction alone cannot establish this table column.


def validate(row):
    d = row["data"]
    if (row["id"] != CID or row["owner"] != "tender-agent"
            or digest(d) != row["hash"] or d.get("canonical_id") != CID
            or d.get("procedure_id") != "351-062" or d.get("scope") != "supply"
            or d.get("quantity") != 2
            or d.get("power") != "3000 кВАр (по опросному листу; не умножать на 2)"
            or d.get("equipment_voltage_kv") is not None
            or d.get("voltage_kv") is not None
            or row["meta"].get("bidzaar_351062_voltage")
            or not any(e.get("url") == CARD_URL for e in d.get("evidence", []))):
        raise RuntimeError("Identity/owner/non-null/source CAS mismatch")


def updated(row):
    data = dict(row["data"])
    data["equipment_voltage_kv"] = VALUE
    data["evidence"] = [*data["evidence"], {
        "url": DOC_URL, "sha256": DOC_SHA, "tier": "first_party_original",
        "field": "equipment_voltage_kv", "value": VALUE,
        "review_method": "human_visual_quicklook_original_DOC",
        "visual_derivative_sha256": VISUAL_SHA}]
    meta = {**row["meta"], "source_content_hash": digest(data),
            "bidzaar_351062_voltage": {
                "field": "equipment_voltage_kv", "value": VALUE,
                "original_sha256": DOC_SHA, "card_sha256": CARD_SHA,
                "visual_derivative_sha256": VISUAL_SHA,
                "review": "DOC nominal voltage row: ДА under 6,3 kV",
                "previous_hash": row["hash"], "previous_revision": row["rev"],
                "warning": "Two tender units; 6000 kvar total and signed supplier unverified"}}
    return data, meta


def apply(row, before):
    data, meta = updated(row)
    new_hash = digest(data)
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
 WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{row['hash']}'
 AND d.revision={row['rev']} AND (d.data->'equipment_voltage_kv') IS NULL)<>1
THEN RAISE EXCEPTION 'PQ CAS/owner/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)}, metadata={js(meta)},
revision=revision+1, updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{row['hash']}'
AND d.revision={row['rev']} AND (d.data->'equipment_voltage_kv') IS NULL;
UPDATE dp_resources SET content_hash='{new_hash}', updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
 WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{new_hash}'
 AND d.revision={row['rev']+1} AND d.data->'equipment_voltage_kv'={js(VALUE)}
 AND d.metadata->'bidzaar_351062_voltage'->>'original_sha256'='{DOC_SHA}')<>1
THEN RAISE EXCEPTION 'PQ postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after, actual = snapshot(), get_row(CID)
    if any(before[k] != after[k] for k in ("rows", "unique", "records")):
        raise RuntimeError("Corpus changed")
    if actual["hash"] != new_hash or actual["rev"] != row["rev"] + 1 or actual["data"] != data:
        raise RuntimeError("Postcommit readback mismatch")
    return {"canonical_id": CID, "before": before, "after": after,
            "new_verified_fields": 1, "old_hash": row["hash"], "new_hash": new_hash,
            "original_sha256": DOC_SHA, "card_sha256": CARD_SHA}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    verified_original()
    before, row = snapshot(), get_row(CID)
    validate(row)
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "id": CID, "before": before,
                          "new_hash": digest(updated(row)[0])}))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Backup and receipt mandatory")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("APFS acceptance failed")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if not backup.get("pg_restore_list_verified") or not 0 <= age <= 1800:
        raise RuntimeError("Fresh verified full backup required")
    result = apply(row, before)
    result["backup_sha256"] = backup["sha256"]
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
