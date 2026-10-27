"""MI-013 v36 primary Meleuz 6.3kV/500kvar three-quote original Excel source.
All three prices are buyer NMC estimates, not registered signed contracts.
Guarded one-existing-row PostgreSQL atomic evidence update; verified backup required.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

from import_pq_postgres_v29 import backup, query, snapshot, COLLECTION, SOURCE, DATA

CID = "223fz:32616296475:lot1"
FILE = "original_meles_6kv_itemized_cost_and_regime_20261028.v36.json"
ACK = "MI013-V36-MELEUZ-20261028"

def source_patch():
    from decimal import Decimal
    doc=json.loads((DATA/FILE).read_text(encoding="utf-8"))
    if (doc["existing_canonical_procurement_cases_enriched"]!=1
       or doc["new_notices"]!=0 or doc["new_registered_signed_contracts"]!=0
       or len(doc["patches"])!=1):
        raise ValueError("v36 requires exactly one existing source patch")
    p=doc["patches"][0]
    prices=p["original_price_justification"]
    tech=p["original_technical"]
    national=p["national_origin_procurement_restriction"]
    if (p["canonical_id"]!=CID or
        p["contractual_scope"]["original_signed_contract_verified"] or
        p["contractual_scope"]["actual_signed_contract_total_rub"] is not None or
        len(p["original_source_files"])!=4 or
        len(prices["units_and_article_quantities"])!=3 or
        prices["equipment_only_reference_mean_rub"]!="3524107.07" or
        prices["original_tender_initial_total_rub"]!="3904773.73" or
        tech["nominal_reactive_power_min_kvar"]!=500 or
        tech["nominal_network_voltage_max_kv"]!=6.3 or
        national["original_table_cell_tick_location"]!="Ограничение" or
        national["is_checkbox_under_prohibition"] or
        not national["is_checkbox_under_limitation"]):
        raise ValueError("original cost, technical or nationality source facts changed")
    lines=prices["units_and_article_quantities"]
    if sum(Decimal(x["buyer_line_average_rub"]) for x in lines)!=Decimal("3904773.73"):
        raise ValueError("original price line means do not reconcile")
    for i in range(3):
        v=sum(Decimal(x["offers_rub"][i]) for x in lines)
        if v!=Decimal(prices["total_per_reference_rub"][i]):
            raise ValueError("source quoted offer subtotal mismatch")
    return p

def fetch():
    rid=hashlib.sha256(CID.encode("utf-8")).hexdigest()[:48]
    sql=f"""BEGIN READ ONLY;
SELECT jsonb_build_object(
 'rid',r.resource_id,'canonical',r.external_id,'uri',r.canonical_uri,
 'source',r.source_type,'collection',r.collection_id,'status',r.status,
 'hash',r.content_hash,'metadata',r.metadata,
 'data',d.data,'record_metadata',d.metadata,'record_type',d.record_type,
 'review',d.review_status,'revision',d.revision
)::text FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.resource_id='{rid}' AND r.collection_id='{COLLECTION}'
 AND r.external_id='223fz:32616296475:lot1';
COMMIT;"""
    a=json.loads(query(sql))
    if a["canonical"]!=CID or a["rid"]!=rid or a["collection"]!=COLLECTION or a["source"]!=SOURCE:
        raise RuntimeError("wrong source identity")
    if a["record_type"]!="pq_procurement_notice_lot" or a["review"]!="unreviewed" or a["status"]!="staged_unreviewed":
        raise RuntimeError("source review status changed")
    return a

def stage(p,a):
    doc=copy.deepcopy(a["data"])
    if "v36" in doc.get("mi013_source_enrichments",{}):
        prev=doc["mi013_source_enrichments"]["v36"]
        if prev.get("verified_primary")!=p:
            raise RuntimeError("v36 already present but content differs")
        digest=hashlib.sha256(json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if digest!=a["hash"]:raise RuntimeError("v36 content hash replay mismatch")
        return {"done":True,"new_hash":digest}
    if a["metadata"]["data_version"]!="v29":
        raise RuntimeError("source row isn't expected v29 baseline; avoid downgrading")
    doc.setdefault("mi013_source_enrichments",{})["v36"]={
        "source_file":FILE,"verified_primary":copy.deepcopy(p),
        "source_grade":"first_party_original_ETP_itemized_XLSX_and_TZ"}
    digest=hashlib.sha256(json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    meta=copy.deepcopy(a["metadata"])
    meta["data_version"]="v36"
    meta["mi013_import_batch"]="v36-20261027"
    meta["research_last_primary_enrichment"]="v36"
    meta["source_evidence_versions"]=sorted(doc["mi013_source_enrichments"])
    meta["source_urls"]=list(dict.fromkeys(meta["source_urls"] + [e["url"] for e in p["original_source_files"]]))
    rec_meta=copy.deepcopy(a["record_metadata"])
    rec_meta.update({"source_content_hash":digest,"source_evidence_urls":meta["source_urls"],"research_version":"v36"})
    return {"done":False,"new_hash":digest,"data":doc,"metadata":meta,"record_metadata":rec_meta}

def build_sql(a,s,old):
    payload={x:json.dumps(s[x],ensure_ascii=False,sort_keys=True,separators=(",",":")).encode().hex() for x in ("data","metadata","record_metadata")}
    return f"""
BEGIN;
SET LOCAL statement_timeout='75s';
SET LOCAL lock_timeout='10s';
SELECT pg_advisory_xact_lock(hashtext('mi013-v36-meleuz-primary-prices'));
DO $guard$
BEGIN
 IF current_database()<>'arvectum_data' OR
    (SELECT owner FROM dp_collections WHERE collection_id='{COLLECTION}')<>'tender-agent' OR
    (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>103 OR
    (SELECT count(*) FROM dp_records WHERE resource_id IN (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>103 THEN
     RAISE EXCEPTION 'tenant or original corpus mismatch';
 END IF;
 IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
    WHERE r.resource_id='{a["rid"]}' AND r.external_id='223fz:32616296475:lot1'
      AND r.canonical_uri='{a["uri"]}' AND r.source_type='{SOURCE}'
      AND r.content_hash='{a["hash"]}' AND d.record_type='pq_procurement_notice_lot'
      AND NOT COALESCE(d.data->'mi013_source_enrichments'?'v36',false))<>1 THEN
     RAISE EXCEPTION 'original source hash or identity drift';
 END IF;
END $guard$;
UPDATE dp_resources SET content_hash='{s["new_hash"]}',
 metadata=convert_from(decode('{payload["metadata"]}','hex'),'UTF8')::jsonb,
 updated_at=now(),last_seen_at=now()
 WHERE resource_id='{a["rid"]}';
UPDATE dp_records SET data=convert_from(decode('{payload["data"]}','hex'),'UTF8')::jsonb,
 metadata=convert_from(decode('{payload["record_metadata"]}','hex'),'UTF8')::jsonb,
 revision=revision+1,updated_at=now()
 WHERE resource_id='{a["rid"]}' AND record_type='pq_procurement_notice_lot';
DO $guard$
BEGIN
 IF (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>103
 OR (SELECT count(*) FROM dp_records WHERE resource_id IN(SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>103
 OR (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
   WHERE r.resource_id='{a["rid"]}' AND r.content_hash='{s["new_hash"]}'
   AND r.metadata->>'data_version'='v36'
   AND d.data->'mi013_source_enrichments'->'v36'->>'source_grade'='first_party_original_ETP_itemized_XLSX_and_TZ')<>1
 OR (SELECT count(*) FROM dp_resources WHERE collection_id<>'{COLLECTION}')<>{old["other_resources"]}
 OR (SELECT count(*) FROM dp_documents)<>{old["all_documents"]} THEN
     RAISE EXCEPTION 'post-update source grade or db count mismatch';
 END IF;
END $guard$;
COMMIT;
SELECT 'MI013_V36_PRIMARY_COST='||count(*) FROM dp_records
 WHERE resource_id='{a["rid"]}' AND data->'mi013_source_enrichments'?'v36';
"""

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--check-db",action="store_true")
    cli.add_argument("--apply",action="store_true")
    cli.add_argument("--approved-command")
    cli.add_argument("--backup-directory",type=Path)
    x=cli.parse_args()
    p=source_patch()
    before=snapshot()
    if before["resources"]!=103 or before["records"]!=103:
        raise RuntimeError("expected exactly 102 PG procurement records")
    rec=fetch()
    change=stage(p,rec)
    print(json.dumps({"version":"v36","id":CID,"already_applied":change["done"],
       "expected_source_grade":"original_first_party","new_hardware_sales":0,
       "new_signed_contracts":0,"source_sha256":change["new_hash"]},ensure_ascii=False),flush=True)
    if not x.apply or change["done"]:return 0
    if x.approved_command!=ACK or not x.backup_directory:
        raise RuntimeError("need approved command and backup directory")
    b=backup(x.backup_directory)
    print(json.dumps({"verified_backup":b},ensure_ascii=False),flush=True)
    res=query(build_sql(rec,change,before),timeout=95)
    if "MI013_V36_PRIMARY_COST=1" not in res: raise RuntimeError("expected commit receipt missing")
    verify=snapshot(); r=fetch(); t=stage(p,r)
    if not t["done"] or verify["resources"]!=103 or verify["records"]!=103 or verify["other_resources"]!=before["other_resources"] or verify["all_documents"]!=before["all_documents"]:
        raise RuntimeError("independent readback failure")
    print(json.dumps({"result":"PASS","new_sha":t["new_hash"],"backup":b,"db_after":verify},ensure_ascii=False),flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
