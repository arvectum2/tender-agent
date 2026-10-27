"""MI-013 v35 one indexed-original Tender.Pro 2023 STATCOM request into PostgreSQL.

Original Tender.Pro page indexed by public search, live first-party returns 503. We
import ONLY a historically published procurement demand signal, not 4 devices
sold, rated 10 kV/35 kV, or a signed contract. Atomic 102-to-103 insert with
independently checksum-verified official PostgreSQL backup before SQL.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from export_pq_data_platform import export_records
from import_pq_postgres_v29 import backup, snapshot, query, COLLECTION, SOURCE, DATA

NEW_ID = "commercial:834269:lot1"
DOC = "original_indexed_tenderpro_rmc_statcom_20261027.v35.json"
ACK = "MI013-V35-ADD-ONE-20261027"


def stage_one():
    d=json.loads((DATA / DOC).read_text(encoding="utf-8"))
    records=d["records"]
    if d["original_notice_count_added"]!=1 or len(records)!=1 or d["signed_contract_count_added"]!=0:
        raise ValueError("one new original-indexed procedure, no original signed contracts")
    r=records[0]
    if (r["canonical_id"]!=NEW_ID or r["procedure_id"]!="834269"
        or r["publication_date"]!="2023-12-06"
        or r["quantity"]!=4 or r["family"]!="statcom"
        or r["equipment"]["nominal_voltage_kv"] is not None
        or r["equipment"]["requested_units"]!=4
        or r["original_bids_submitted"] is not None
        or r["commission_winner"] is not None
        or r["nmck_rub"] is not None
        or r["registered_signed_contract_verified"] is not False
        or r["actual_signed_contract_price_rub"] is not None
        or r["source_grade"]!="original_ETP_public_page_cached_by_search_engine_not_directly_retrieved"
        or r["direct_first_party_http_result"].find("503")<0):
        raise ValueError("source grade, equipment voltage or award is not verified")
    if not any(x["source_tier"]=="first_party_ETP_original_public_card_search_engine_indexed"
               and x["url"].startswith("https://www.tender.pro/api/tender/834269")
               for x in r["evidence"]):
        raise ValueError("no first-party page search-indexed pointer")
    row=export_records({"records":records,"data_version":"v35",
                        "verification_summary":{"total_lot_level_records":1}})[0]
    if row["external_id"]!=NEW_ID:
        raise ValueError("canonical ID drift in exporter")
    row["metadata"]["source_evidence_versions"]=["v35"]
    row["metadata"]["research_original_url_checked"]=False
    row["metadata"]["source_grade"]="indexed_first_party_ETP_503_live_inaccessible"
    row["metadata"]["mi013_import_batch"]="v35-20261027"
    return row

def has_new(row):
    rid=row["resource_id"]
    out=query(f"""BEGIN READ ONLY;
SELECT jsonb_build_object(
 'resource_id',r.resource_id,'external_id',r.external_id,'canonical_uri',r.canonical_uri,
 'collection',r.collection_id,'source',r.source_type,'status',r.status,
 'content_hash',r.content_hash,'version',r.metadata->>'data_version',
 'record_type',d.record_type,'review_status',d.review_status,
 'bid_count',d.data->>'original_bids_submitted','winner',d.data->>'commission_winner',
 'contract',d.data->>'actual_signed_contract_price_rub')::text
FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.external_id='{NEW_ID}' OR r.resource_id='{rid}' OR r.canonical_uri='{row["canonical_uri"]}';
COMMIT;""")
    if not out:
        return None
    v=json.loads(out)
    expected={
      "resource_id":row["resource_id"],"external_id":NEW_ID,"canonical_uri":row["canonical_uri"],
      "collection":COLLECTION,"source":SOURCE,"status":"staged_unreviewed",
      "content_hash":row["content_hash"],"version":"v35",
      "record_type":"pq_procurement_notice_lot","review_status":"unreviewed",
      "bid_count":None,"winner":None,"contract":None
    }
    if v != expected:
        raise RuntimeError("refuse existing ambiguous/colliding canonical v35 row "+str(v)[:480])
    return v


def sql_for(row, before):
    content=json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8").hex()
    return f"""
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='90s';
SELECT pg_advisory_xact_lock(hashtext('mi013-pq-v35-add-indexed-original-2023-statcom'));
CREATE TEMP TABLE mi013_new (item jsonb NOT NULL) ON COMMIT DROP;
INSERT INTO mi013_new VALUES (convert_from(decode('{content}','hex'),'UTF8')::jsonb);
DO $guard$
BEGIN
 IF current_database()<>'arvectum_data'
 OR (SELECT owner FROM dp_collections WHERE collection_id='{COLLECTION}')<>'tender-agent'
 OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>102
 OR (SELECT count(*) FROM dp_records WHERE resource_id IN
      (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>102 THEN
   RAISE EXCEPTION 'wrong database owner or corpus count';
 END IF;
 IF (SELECT count(*) FROM mi013_new)<>1 OR
    (SELECT count(*) FROM mi013_new WHERE item->>'external_id'='{NEW_ID}'
     AND item->>'collection_id'='{COLLECTION}'
     AND item->>'source_type'='{SOURCE}'
     AND item->>'status'='staged_unreviewed'
     AND item->'metadata'->>'data_version'='v35')<>1 THEN
    RAISE EXCEPTION 'new original source staged data mismatch';
 END IF;
 IF EXISTS(
  SELECT 1 FROM mi013_new s JOIN dp_resources r
  ON r.resource_id=s.item->>'resource_id'
  OR r.external_id=s.item->>'external_id'
  OR r.canonical_uri=s.item->>'canonical_uri'
 ) THEN RAISE EXCEPTION 'new procurement duplicates existing canonical URI/ID'; END IF;
END $guard$;
INSERT INTO dp_resources(
 resource_id,collection_id,source_type,canonical_uri,external_id,content_hash,status,
 metadata,refresh_policy,first_seen_at,last_seen_at,created_at,updated_at)
SELECT item->>'resource_id',item->>'collection_id',item->>'source_type',
 item->>'canonical_uri',item->>'external_id',item->>'content_hash',
 item->>'status',item->'metadata','{{}}'::jsonb,now(),now(),now(),now()
FROM mi013_new;
INSERT INTO dp_records(
 record_id,resource_id,record_type,data,revision,review_status,metadata,created_at,updated_at)
SELECT 'pq:'||(item->>'resource_id'),item->>'resource_id',
 'pq_procurement_notice_lot',item->'source_record',1,'unreviewed',
 jsonb_build_object('source_content_hash',item->>'content_hash',
                    'source_evidence_urls',item->'metadata'->'source_urls',
                    'research_version','v35'),now(),now()
FROM mi013_new;
DO $guard$
BEGIN
 IF (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>103
 OR (SELECT count(*) FROM dp_records WHERE resource_id IN
      (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>103
 OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COLLECTION}')<>103
 OR (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
     WHERE r.collection_id='{COLLECTION}' AND r.external_id='{NEW_ID}'
       AND r.metadata->>'data_version'='v35'
       AND d.data->>'original_bids_submitted' IS NULL
       AND d.data->>'registered_signed_contract_verified'='false'
       AND d.data->'equipment'->>'requested_units'='4'
       AND d.data->'equipment'->>'nominal_voltage_kv' IS NULL)<>1 THEN
  RAISE EXCEPTION 'v35 postwrite wrong count or correctly source-graded demand signal';
 END IF;
 IF (SELECT count(*) FROM dp_resources WHERE collection_id<>'{COLLECTION}')<>{before['other_resources']}
 OR (SELECT count(*) FROM dp_records WHERE resource_id NOT IN
     (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>{before['other_records']}
 OR (SELECT count(*) FROM dp_documents)<>{before['all_documents']} THEN
   RAISE EXCEPTION 'unrelated Data Platform collections changed';
 END IF;
END $guard$;
COMMIT;
SELECT 'MI013_V35_RESOURCES='||count(*) FROM dp_resources WHERE collection_id='{COLLECTION}';
"""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--check-db",action="store_true")
    parser.add_argument("--approved-command")
    parser.add_argument("--backup-directory",type=Path)
    a=parser.parse_args()
    row=stage_one()
    before=snapshot()
    existing=has_new(row)
    report={"version":"v35","candidate":NEW_ID,"new_notices":0 if existing else 1,
      "db_before":before["resources"],"row_hash":row["content_hash"],
      "status":"already_imported_idempotent" if existing else "ready_to_insert"}
    if existing:
        if before["resources"]!=103 or before["records"]!=103:
            raise RuntimeError("found existing candidate but corpus cardinality not 103")
        print(json.dumps(report,ensure_ascii=False,sort_keys=True),flush=True)
        return 0
    if before["resources"]!=102 or before["records"]!=102:
        raise RuntimeError("wrong v34 baseline cardinality")
    print(json.dumps(report,ensure_ascii=False,sort_keys=True),flush=True)
    if not a.apply:
        return 0
    if a.approved_command != ACK or a.backup_directory is None:
        raise RuntimeError("missing explicit agreed batch and official backup location")
    proof=backup(a.backup_directory)
    print(json.dumps({"backup_verified":proof},ensure_ascii=False,sort_keys=True),flush=True)
    result=query(sql_for(row,before),timeout=115)
    if "MI013_V35_RESOURCES=103" not in result:
        raise RuntimeError("postcommit resource count receipt missing")
    after=snapshot()
    verify=has_new(row)
    if (not verify or after["resources"]!=103 or after["records"]!=103
        or after["unique_ids"]!=103 or after["other_resources"]!=before["other_resources"]
        or after["other_records"]!=before["other_records"]
        or after["all_documents"]!=before["all_documents"]):
        raise RuntimeError("postcommit independently verified count mismatched")
    print(json.dumps({"result":"PASS","backup":proof,"after":after,
           "imported_row_hash":row["content_hash"]},ensure_ascii=False,sort_keys=True),flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
