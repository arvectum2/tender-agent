"""MI-013 v34: append provenance-graded secondary 10kV Novatek BOM to one PG case.

Do NOT mistake a reposted commercial ETP position table for independently
verified buyer's technical XLSX / signed original contract.
Dry run by default. Approved apply creates SHA-verified official pg_dump.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

from import_pq_postgres_v29 import backup, query, snapshot, COLLECTION, SOURCE, DATA

CID = "commercial:ГП630876:lot1"
FILE = "secondary_etgpb_novatek_bom_20261027.v34.json"
ACK = "MI013-V34-GP630876-20261027"

def source_patch():
    f=json.loads((DATA / FILE).read_text(encoding="utf-8"))
    if f["changes_count"]!=1 or f["new_procurement_notices"]!=0 or len(f["patches"])!=1:
        raise ValueError("one-existing-record source patch only")
    p=f["patches"][0]
    if (p["canonical_id"]!=CID or p["supplier_name_verified"] or p["signed_contract_verified"]
        or p["source_original_ETP_7z_files_verified"]
        or p["signed_contract_rub"] is not None
        or len(p["bill_of_quantities_visible_board"])!=10
        or p["quantity_cross_checks"]["switching_reactors_total"]!=8
        or p["quantity_cross_checks"]["fuses_total"]!=18):
        raise ValueError("source grade, BOM or unsigned status mismatch")
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
 AND r.external_id='commercial:ГП630876:lot1';
COMMIT;"""
    a=json.loads(query(sql))
    if a["canonical"]!=CID or a["rid"]!=rid or a["collection"]!=COLLECTION or a["source"]!=SOURCE:
        raise RuntimeError("wrong source identity")
    if a["record_type"]!="pq_procurement_notice_lot" or a["review"]!="unreviewed" or a["status"]!="staged_unreviewed":
        raise RuntimeError("source review status changed")
    return a

def stage(p,a):
    doc=copy.deepcopy(a["data"])
    if "v34" in doc.get("mi013_source_enrichments",{}):
        prev=doc["mi013_source_enrichments"]["v34"]
        if prev.get("verified_secondary")!=p:
            raise RuntimeError("v34 already present but content differs")
        digest=hashlib.sha256(json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if digest!=a["hash"]:raise RuntimeError("v34 content hash replay mismatch")
        return {"done":True,"new_hash":digest}
    if a["metadata"]["data_version"]!="v29":
        raise RuntimeError("source row isn't expected v29 baseline; avoid downgrading")
    doc.setdefault("mi013_source_enrichments",{})["v34"]={
        "source_file":FILE,"verified_secondary":copy.deepcopy(p),
        "source_grade":"secondary_platform_reprint_not_primary_archive"}
    digest=hashlib.sha256(json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    meta=copy.deepcopy(a["metadata"])
    meta["data_version"]="v34"
    meta["mi013_import_batch"]="v34-20261027"
    meta["research_last_secondary_enrichment"]="v34"
    meta["source_evidence_versions"]=sorted(doc["mi013_source_enrichments"])
    meta["source_urls"]=list(dict.fromkeys(meta["source_urls"] + [e["url"] for e in p["source"]]))
    rec_meta=copy.deepcopy(a["record_metadata"])
    rec_meta.update({"source_content_hash":digest,"source_evidence_urls":meta["source_urls"],"research_version":"v34"})
    return {"done":False,"new_hash":digest,"data":doc,"metadata":meta,"record_metadata":rec_meta}

def build_sql(a,s,old):
    payload={x:json.dumps(s[x],ensure_ascii=False,sort_keys=True,separators=(",",":")).encode().hex() for x in ("data","metadata","record_metadata")}
    return f"""
BEGIN;
SET LOCAL statement_timeout='75s';
SET LOCAL lock_timeout='10s';
SELECT pg_advisory_xact_lock(hashtext('mi013-v34-novatek-partial-BOM'));
DO $guard$
BEGIN
 IF current_database()<>'arvectum_data' OR
    (SELECT owner FROM dp_collections WHERE collection_id='{COLLECTION}')<>'tender-agent' OR
    (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>102 OR
    (SELECT count(*) FROM dp_records WHERE resource_id IN (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>102 THEN
     RAISE EXCEPTION 'tenant or original corpus mismatch';
 END IF;
 IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
    WHERE r.resource_id='{a["rid"]}' AND r.external_id='commercial:ГП630876:lot1'
      AND r.canonical_uri='{a["uri"]}' AND r.source_type='{SOURCE}'
      AND r.content_hash='{a["hash"]}' AND d.record_type='pq_procurement_notice_lot'
      AND NOT COALESCE(d.data->'mi013_source_enrichments'?'v34',false))<>1 THEN
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
 IF (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>102
 OR (SELECT count(*) FROM dp_records WHERE resource_id IN(SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>102
 OR (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
   WHERE r.resource_id='{a["rid"]}' AND r.content_hash='{s["new_hash"]}'
   AND r.metadata->>'data_version'='v34'
   AND d.data->'mi013_source_enrichments'->'v34'->>'source_grade'='secondary_platform_reprint_not_primary_archive')<>1
 OR (SELECT count(*) FROM dp_resources WHERE collection_id<>'{COLLECTION}')<>{old["other_resources"]}
 OR (SELECT count(*) FROM dp_documents)<>{old["all_documents"]} THEN
     RAISE EXCEPTION 'post-update source grade or db count mismatch';
 END IF;
END $guard$;
COMMIT;
SELECT 'MI013_V34_SECONDARY_BOM='||count(*) FROM dp_records
 WHERE resource_id='{a["rid"]}' AND data->'mi013_source_enrichments'?'v34';
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
    if before["resources"]!=102 or before["records"]!=102:
        raise RuntimeError("expected exactly 102 PG procurement records")
    rec=fetch()
    change=stage(p,rec)
    print(json.dumps({"version":"v34","id":CID,"already_applied":change["done"],
       "expected_source_grade":"secondary","new_hardware_sales":0,
       "new_signed_contracts":0,"source_sha256":change["new_hash"]},ensure_ascii=False),flush=True)
    if not x.apply or change["done"]:return 0
    if x.approved_command!=ACK or not x.backup_directory:
        raise RuntimeError("need approved command and backup directory")
    b=backup(x.backup_directory)
    print(json.dumps({"verified_backup":b},ensure_ascii=False),flush=True)
    res=query(build_sql(rec,change,before),timeout=95)
    if "MI013_V34_SECONDARY_BOM=1" not in res: raise RuntimeError("expected commit receipt missing")
    verify=snapshot(); r=fetch(); t=stage(p,r)
    if not t["done"] or verify["resources"]!=102 or verify["records"]!=102 or verify["other_resources"]!=before["other_resources"] or verify["all_documents"]!=before["all_documents"]:
        raise RuntimeError("independent readback failure")
    print(json.dumps({"result":"PASS","new_sha":t["new_hash"],"backup":b,"db_after":verify},ensure_ascii=False),flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
