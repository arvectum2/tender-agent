"""MI-013 v31 source-verified *single-record* PostgreSQL evidence enrichment.

Read-only by default. Imports original 2024 220kV EPC bidder ranking only into
its PREEXISTING 32413581034 notice without appending a fake sixth contract or
extra procurement notice. Requires official SHA256-verified prewrite backup.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json

from pathlib import Path
from import_pq_postgres_v29 import (
    COLLECTION, DATA, SOURCE, backup, query, snapshot, stage
)

ID = "223fz:32413581034:lot2"
DOCUMENT = "primary_2024_khani_epc_original_award_20261027.v31.json"
ACK = "MI013-V31-KHANI-20261027"


def prepare():
    files = json.loads((DATA / DOCUMENT).read_text(encoding="utf-8"))
    if files["existing_notices_enriched"] != 1 or files["new_legal_procurement_notices"] != 0:
        raise ValueError("v31 patch count incompatible with canonical corpus")
    patches = files["patches"]
    if len(patches) != 1 or patches[0]["canonical_id"] != ID:
        raise ValueError("v31 canonical ID changed")
    a = patches[0]
    if (
        a["signed_original_rd223_contract_verified"] is not False
        or a["actual_PQ_equipment_only_contract_value_rub"] is not None
        or a["actual_registered_signed_price_rub"] is not None
        or len(a["original_bidders"]) != 2
        or a["high_voltage_adjacent_220kv_epc"] is not True
    ):
        raise ValueError("unsupported signed sale or market population evidence")
    rows = stage()
    x = next((r for r in rows if r["external_id"] == ID), None)
    if len(rows) != 101 or x is None:
        raise ValueError("canonical v29 dataset lacks 2024 EPC record")
    row = copy.deepcopy(x["source_record"])
    if "v31" in row.get("mi013_source_enrichments", {}):
        raise ValueError("v31 already embedded unexpectedly in v29 original")
    row.setdefault("mi013_source_enrichments", {})["v31"] = {
        "source_file": DOCUMENT,
        "verified_original": copy.deepcopy(a),
    }
    raw = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    urls = list(dict.fromkeys(x["metadata"]["source_urls"] + [e["url"] for e in a["sources"]]))
    if any(not u.startswith("https://") for u in urls):
        raise ValueError("source link invalid")
    meta = {
        "source_urls": urls,
        "source_evidence_versions": sorted(row["mi013_source_enrichments"]),
        "research_last_primary_enrichment": "v31",
        "mi013_import_batch": "v31-20261027",
        "data_version": "v31",
    }
    return x, row, meta, digest


def read_target(x):
    rid = x["resource_id"]
    sql = f"""BEGIN READ ONLY;
SELECT jsonb_build_object(
 'resource_hash',r.content_hash,
 'resource_id',r.resource_id,
 'canonical_id',r.external_id,
 'collection',r.collection_id,
 'source',r.source_type,
 'record_type',d.record_type,
 'review_status',d.review_status,
 'revision',d.revision,
 'has_v31',coalesce(d.data->'mi013_source_enrichments'?'v31',false),
 'metadata_version',r.metadata->>'data_version'
)::text
FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.resource_id='{rid}';
COMMIT;"""
    return json.loads(query(sql))


def make_sql(x, row, meta, newhash, before):
    rid = x["resource_id"]
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8").hex()
    metadata = json.dumps(meta, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8").hex()
    baseline = x["content_hash"]
    return f"""
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SELECT pg_advisory_xact_lock(hashtext('mi013-pq-v31-single-source'));
DO $guard$
BEGIN
 IF current_database()<>'arvectum_data' THEN
   RAISE EXCEPTION 'not allowed database';
 END IF;
 IF (SELECT owner FROM dp_collections WHERE collection_id='{COLLECTION}')<>'tender-agent' THEN
   RAISE EXCEPTION 'owner guard';
 END IF;
 IF (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>101 OR
    (SELECT count(*) FROM dp_records WHERE resource_id IN
    (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>101 THEN
   RAISE EXCEPTION 'pq corpus changed';
 END IF;
 IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
     WHERE r.resource_id='{rid}' AND r.collection_id='{COLLECTION}'
       AND r.source_type='{SOURCE}' AND r.external_id='{ID}'
       AND r.canonical_uri='{x['canonical_uri']}'
       AND r.content_hash='{baseline}'
       AND d.record_type='pq_procurement_notice_lot'
       AND d.review_status='unreviewed'
       AND NOT(d.data->'mi013_source_enrichments'?'v31'))<>1 THEN
   RAISE EXCEPTION 'original single record mismatch, refusing to apply';
 END IF;
END $guard$;
UPDATE dp_resources
 SET content_hash='{newhash}',metadata=metadata||convert_from(decode('{metadata}','hex'),'UTF8')::jsonb,
     last_seen_at=now(),updated_at=now()
 WHERE resource_id='{rid}';
UPDATE dp_records
 SET data=convert_from(decode('{payload}','hex'),'UTF8')::jsonb,
     revision=revision+1,
     metadata=metadata||jsonb_build_object(
       'source_content_hash','{newhash}','research_version','v31'),
     updated_at=now()
 WHERE resource_id='{rid}' AND record_type='pq_procurement_notice_lot';
DO $guard$
BEGIN
 IF (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>101 OR
    (SELECT count(*) FROM dp_records WHERE resource_id IN
    (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>101 OR
    (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
      WHERE r.resource_id='{rid}' AND r.content_hash='{newhash}'
      AND d.data->'mi013_source_enrichments'?'v31')<>1 THEN
   RAISE EXCEPTION 'v31 provenance/record count mismatch';
 END IF;
 IF (SELECT count(*) FROM dp_resources WHERE collection_id<>'{COLLECTION}')<>{before['other_resources']} OR
    (SELECT count(*) FROM dp_documents)<>{before['all_documents']} THEN
   RAISE EXCEPTION 'another collection drift';
 END IF;
END $guard$;
COMMIT;
SELECT 'MI013_V31_ENRICHED='||count(*)
FROM dp_records WHERE resource_id='{rid}'
 AND data->'mi013_source_enrichments'?'v31';
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check-db", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--approved-command", default=None)
    p.add_argument("--backup-directory", type=Path)
    args=p.parse_args()
    x,row,meta,digest=prepare()
    summary={"stage":"v31","existing_procurement_id":ID,"new_notices":0,
             "new_named_company_occurrences":2,"signed_original_contract_delta":0,
             "previous_source_hash":x["content_hash"],"new_source_hash":digest}
    if args.check_db or args.apply:
        before=snapshot()
        r=read_target(x)
        if before["resources"]!=101 or before["records"]!=101:
            raise RuntimeError("expected fully synced PQ 101")
        if r["resource_id"]!=x["resource_id"] or r["canonical_id"]!=ID or r["collection"]!=COLLECTION:
            raise RuntimeError("target identity changed")
        if r["has_v31"] and r["resource_hash"]==digest:
            summary["status"]="already-applied-idempotent"
            print(json.dumps(summary,ensure_ascii=False),flush=True)
            return 0
        if r["has_v31"] or r["resource_hash"]!=x["content_hash"]:
            raise RuntimeError(f"source record drift {r}")
        summary["status"]="ready-to-update-one-existing-record"
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    if not args.apply:
        return 0
    if args.approved_command != ACK or args.backup_directory is None:
        raise RuntimeError("explicit owner-approved batch and backup location required")
    proof=backup(args.backup_directory)
    print(json.dumps({"backup_verified":proof},ensure_ascii=False),flush=True)
    out=query(make_sql(x,row,meta,digest,before))
    if "MI013_V31_ENRICHED=1" not in out:
        raise RuntimeError("transaction receipt missing, inspect database")
    after=snapshot()
    target=read_target(x)
    if (after["resources"]!=101 or after["records"]!=101 or
            after["other_resources"]!=before["other_resources"] or
            after["all_documents"]!=before["all_documents"] or
            not target["has_v31"] or target["resource_hash"]!=digest):
        raise RuntimeError("postcommit original evidence readback discrepancy")
    print(json.dumps({"result":"PASS","new_hash":digest,"target":target,"db_after":after,"backup":proof},ensure_ascii=False),flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
