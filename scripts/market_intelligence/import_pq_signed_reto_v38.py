"""Import one first-party signed RD223 12kV capacitor case, atomically and with backup."""
import argparse,json
from pathlib import Path
from export_pq_data_platform import export_records
from import_pq_postgres_v29 import DATA,COLLECTION,SOURCE,backup,query,snapshot

ID="223fz:32616181358:lot1"
FILE="original_signed_12kv_reto_20261028.v38.json"
ACK="MI013-V38-RETO-20261028"

def staged():
    x=json.loads((DATA/FILE).read_text(encoding="utf8"))
    p=x["records"][0]
    assert x["new_original_registered_signed_contracts"]==1 and x["original_single_new_notice_count"]==1
    assert p["canonical_id"]==ID and p["registered_signed_contract_verified"]
    assert p["registry_contract"]["signed_contract_registry_verified"]
    assert p["registry_contract"]["registry_number"]=="57724646338260000460000"
    assert p["actual_signed_contract_price_rub"]=="3050000.00"
    assert p["quantity"]==10 and p["equipment"]["nominal_voltage_kv"]==12
    assert sum(int(v["units"])*int(v["unit_price_rub"].split(".")[0]) for v in p["product_lines"])==3050000
    assert p["supplier_inn"] is None and p["delivered_verified"] is False
    row=export_records({"records":[p],"data_version":"v38","verification_summary":{"total_lot_level_records":1}})[0]
    row["metadata"].update({"source_evidence_versions":["v38"],"research_original_url_checked":True,"mi013_import_batch":"v38-20261028"})
    return row

def check(row):
    x=query("SELECT content_hash FROM dp_resources WHERE external_id='"+ID+"' AND collection_id='"+COLLECTION+"';")
    if not x:return False
    if x.strip()!=row["content_hash"]:raise RuntimeError("existing original signed row SHA mismatch")
    j=query("SELECT d.data->>'registered_contract_number',d.data->>'actual_signed_contract_price_rub' FROM dp_records d JOIN dp_resources r USING(resource_id) WHERE r.external_id='"+ID+"';",delimiter="|")
    if j.strip()!="57724646338260000460000|3050000.00":raise RuntimeError("existing signed source data not verified")
    return True

def apply(row,old):
    h=json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode().hex()
    rid=row["resource_id"]
    sql=f"""
BEGIN;
SET LOCAL statement_timeout='90s';
SELECT pg_advisory_xact_lock(hashtext('mi013-12kv-reto-original-signed-v38'));
CREATE TEMP TABLE source(item jsonb NOT NULL) ON COMMIT DROP;
INSERT INTO source VALUES(convert_from(decode('{h}','hex'),'UTF8')::jsonb);
DO $g$ BEGIN
 IF current_database()<>'arvectum_data'
 OR (SELECT owner FROM dp_collections WHERE collection_id='{COLLECTION}')<>'tender-agent'
 OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>103
 OR (SELECT count(*) FROM dp_records WHERE resource_id IN (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>103
 OR EXISTS(SELECT 1 FROM dp_resources WHERE external_id='{ID}' OR resource_id='{rid}')
 THEN RAISE EXCEPTION 'source row duplicate or baseline changed'; END IF;
END $g$;
INSERT INTO dp_resources(resource_id,collection_id,source_type,canonical_uri,external_id,content_hash,status,metadata,refresh_policy,first_seen_at,last_seen_at,created_at,updated_at)
SELECT item->>'resource_id',item->>'collection_id',item->>'source_type',item->>'canonical_uri',item->>'external_id',item->>'content_hash',item->>'status',item->'metadata','{{}}'::jsonb,now(),now(),now(),now() FROM source;
INSERT INTO dp_records(record_id,resource_id,record_type,data,revision,review_status,metadata,created_at,updated_at)
SELECT 'pq:'||(item->>'resource_id'),item->>'resource_id','pq_procurement_notice_lot',item->'source_record',1,'unreviewed',jsonb_build_object('source_content_hash',item->>'content_hash','source_evidence_urls',item->'metadata'->'source_urls','research_version','v38'),now(),now() FROM source;
DO $g$ BEGIN
 IF (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>104
 OR (SELECT count(*) FROM dp_records WHERE resource_id IN(SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>104
 OR (SELECT count(*) FROM dp_resources WHERE collection_id<>'{COLLECTION}')<>{old["other_resources"]}
 OR (SELECT count(*) FROM dp_documents)<>{old["all_documents"]}
 OR (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id) WHERE r.external_id='{ID}'
   AND r.content_hash='{row["content_hash"]}'
   AND d.data->>'registered_signed_contract_verified'='true'
   AND d.data->>'actual_signed_contract_price_rub'='3050000.00'
   AND d.data->'registry_contract'->>'registry_number'='57724646338260000460000')<>1
 THEN RAISE EXCEPTION 'post-write signed registry or tenant count error'; END IF;
END $g$;
COMMIT;
SELECT 'V38_DONE='||count(*) FROM dp_resources WHERE collection_id='{COLLECTION}';
"""
    result=query(sql,timeout=115)
    if "V38_DONE=104" not in result:raise RuntimeError("commit receipt missing")

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--apply",action="store_true")
    cli.add_argument("--approved-command")
    cli.add_argument("--backup-directory",type=Path)
    a=cli.parse_args()
    row=staged()
    before=snapshot()
    already=check(row)
    print(json.dumps({"before":before["resources"],"new":0 if already else 1,"signed_contract":ID,"sha":row["content_hash"]},ensure_ascii=False),flush=True)
    if already:
        assert before["resources"]==before["records"]==104
        return
    if before["resources"]!=103 or before["records"]!=103:raise RuntimeError("unexpected baseline")
    if not a.apply:return
    if a.approved_command!=ACK or a.backup_directory is None:raise RuntimeError("not approved backup batch")
    proof=backup(a.backup_directory)
    print(json.dumps({"verified_backup":proof}),flush=True)
    apply(row,before)
    after=snapshot()
    if not check(row) or after["resources"]!=104 or after["records"]!=104 or after["unique_ids"]!=104:
        raise RuntimeError("post-commit verification failed")
    if any(after[x]!=before[x] for x in ["other_resources","other_records","all_documents"]):
        raise RuntimeError("other collection changed")
    print(json.dumps({"result":"PASS","after":after,"backup":proof},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
