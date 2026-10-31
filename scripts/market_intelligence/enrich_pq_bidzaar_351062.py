"""Source-SHA/CAS guarded one-case Bidzaar 351-062 P2 power enrichment."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from docx import Document

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
           "6b83bcd1-b7a6-4347-8277-3afab3c7c35a/300240128.docx")
CARD_REL = "captures/commercial_351-062_lot1/20261031T143251617646Z-b428ec83-097d69a3e4aaff20.bin"
DOC_REL = "captures/commercial_351-062_lot1/20261031T143542740162Z-984d258a-e53a74ef8a4fda14.bin"
CARD_SHA = "097d69a3e4aaff20b38fbe6c5e1ef83263fc2ab567b9004ceb869e7ff2e27894"
DOC_SHA = "e53a74ef8a4fda14aedce7254488013187aba3bba7780b5a9c6443e4d0caacaf"
QUOTE = "УКРМ на 3000 кВАр , должен быть отдельно стоящий."
VALUE = "3000 кВАр (по опросному листу; не умножать на 2)"
INTERNAL = Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live")


def verified_original():
    if ROOT.resolve(strict=True) != INTERNAL:
        raise RuntimeError("External source root forbidden")
    card, doc = INTERNAL / CARD_REL, INTERNAL / DOC_REL
    for path, sha in ((card, CARD_SHA), (doc, DOC_SHA)):
        if path.is_symlink() or path.stat().st_size > 3_000_000:
            raise RuntimeError("Unsafe source")
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise RuntimeError("Source SHA drift")
    card_html = card.read_text(encoding="utf-8")
    if CARD_URL.rsplit("/", 1)[-1] not in card_html or DOC_URL.split("/")[-2] not in card_html:
        raise RuntimeError("Bidzaar card does not bind original attachment")
    paragraphs = [p.text.strip() for p in Document(doc).paragraphs]
    if QUOTE not in paragraphs or 'Проект: ПС 35/6 кВ "ПОСКО"' not in paragraphs:
        raise RuntimeError("Technical quote absent")


def validate(row):
    if row["id"] != CID or row["owner"] != "tender-agent":
        raise RuntimeError("Identity/owner mismatch")
    if digest(row["data"]) != row["hash"]:
        raise RuntimeError("Content hash mismatch")
    if row["data"].get("power") is not None or row["data"].get("quantity") != 2:
        raise RuntimeError("Non-null field or quantity conflict")
    if not any(e.get("url") == CARD_URL for e in row["data"].get("evidence", [])):
        raise RuntimeError("Source card not bound to lot")
    if "bidzaar_351062_p2" in row["meta"]:
        raise RuntimeError("Prior enrichment")


def updated(row):
    data = dict(row["data"])
    data["power"] = VALUE
    data["evidence"] = [*data["evidence"], {
        "url": DOC_URL, "sha256": DOC_SHA, "tier": "first_party_original",
        "field": "power", "quote": QUOTE}]
    meta = {**row["meta"], "source_content_hash": digest(data),
            "bidzaar_351062_p2": {
                "field": "power", "value": VALUE, "original_sha256": DOC_SHA,
                "card_sha256": CARD_SHA, "exact_quote": QUOTE,
                "previous_hash": row["hash"], "previous_revision": row["rev"],
                "warning": "Two tender units; total kvar and signed contract unverified"}}
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
 AND d.revision={row['rev']} AND (d.data->'power') IS NULL)<>1
THEN RAISE EXCEPTION 'PQ CAS/owner/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)}, metadata={js(meta)},
revision=revision+1, updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{row['hash']}'
AND d.revision={row['rev']} AND (d.data->'power') IS NULL;
UPDATE dp_resources SET content_hash='{new_hash}', updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
 WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{new_hash}'
 AND d.revision={row['rev']+1} AND d.data->'power'={js(VALUE)}
 AND d.metadata->'bidzaar_351062_p2'->>'original_sha256'='{DOC_SHA}')<>1
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
