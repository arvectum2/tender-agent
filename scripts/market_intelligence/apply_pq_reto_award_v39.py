"""MI-013 v39: original ETP awarded bidder enrichment for existing signed 223FZ EIS contract."""
import argparse,copy,hashlib,json
from pathlib import Path
from import_pq_postgres_v29 import DATA,COLLECTION,SOURCE,backup,query,snapshot
CID="223fz:32616181358:lot1"
FILE="original_reto_2026_competition_winner_20261028.v39.json"
ACK="MI013-V39-RETO-WINNER-20261028"

def proof():
    x=json.loads((DATA/FILE).read_text(encoding="utf8"))
    p=x["patches"][0]
    if x["existing_cases_enriched"]!=1 or x["new_signed_contracts"]!=0 or x["new_procurement_notices"]!=0:
        raise ValueError("v39 can only enrich the existing signed source")
    if (p["canonical_id"]!=CID or p["bids_received"]!=3 or p["bids_admitted"]!=2
       or p["bids_rejected"]!=1 or p["rd223_signed_total_rub"]!="3050000.00"
       or p["corresponding_original_rd223_contract"]!="57724646338260000460000"
       or p["original_pdf"]["sha256"]!="92874d098feb7dc6c283bd7b66c5218e11e472f27eddffc75edd6613fb5b21ef"
       or p["participants"][0]["inn"]!="7720494275"
       or p["participants"][1]["inn"]!="7721814062"
       or p["participants"][2]["inn"]!="5043061102"
       or not p["awarded_bidder_identity_verified_on_ETP_protocol"]
       or p["actual_signed_supplier_identity_disclosed_on_rd223_public_card"]):
        raise ValueError("original contract/winner/factory provenance conflict")
    return p

def fetch():
    rid=hashlib.sha256(CID.encode("utf8")).hexdigest()[:48]
    row=query(f"SELECT jsonb_build_object('rid',r.resource_id,'cid',r.external_id,'hash',r.content_hash,'meta',r.metadata,'data',d.data,'rmeta',d.metadata,'revision',d.revision)::text FROM dp_resources r JOIN dp_records d USING(resource_id) WHERE r.collection_id='{COLLECTION}' AND r.resource_id='{rid}' AND r.external_id='{CID}';")
    if not row:raise RuntimeError("registered 104th original source case absent")
    return json.loads(row)

def stage(p,old):
    d=copy.deepcopy(old["data"])
    if (d["registered_signed_contract_verified"] is not True or
        d["registry_contract"]["registry_number"]!="57724646338260000460000" or
        d["actual_signed_contract_price_rub"]!="3050000.00" or
        d["supplier_inn"] is not None):
        raise ValueError("signed original source immutable invariant failed")
    if "v39" in d.get("mi013_source_enrichments",{}):
        if d["mi013_source_enrichments"]["v39"]["verified_primary"]!=p:
            raise ValueError("v39 materialized source mismatch")
        h=hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if old["hash"]!=h:raise ValueError("existing v39 source content digest drift")
        return {"done":True,"hash":h}
    if old["meta"]["data_version"]!="v38":
        raise ValueError("refuse overwriting prior original/enriched source")
    d.setdefault("mi013_source_enrichments",{})["v39"]={
        "source_file":FILE,"verified_primary":copy.deepcopy(p),
        "source_grade":"first_party_original_ETP_signed_final_protocol_PDF"}
    h=hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    m=copy.deepcopy(old["meta"])
    m.update({"data_version":"v39","mi013_import_batch":"v39-20261028",
        "source_evidence_versions":sorted(d["mi013_source_enrichments"])})
    m["source_urls"]=list(dict.fromkeys(m["source_urls"]+[p["original_pdf"]["url"]]))
    rm=copy.deepcopy(old["rmeta"])
    rm.update({"research_version":"v39","source_content_hash":h,"source_evidence_urls":m["source_urls"]})
    return {"done":False,"hash":h,"data":d,"meta":m,"rmeta":rm}

def atomic_write(old,s,before):
    def hexjson(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode().hex()
    sql=f"""
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='90s';
SELECT pg_advisory_xact_lock(hashtext('mi013-v39-retro-original-award'));
DO $guard$ BEGIN
 IF current_database()<>'arvectum_data'
 OR (SELECT owner FROM dp_collections WHERE collection_id='{COLLECTION}')<>'tender-agent'
 OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>104
 OR (SELECT count(*) FROM dp_records WHERE resource_id IN (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>104
 OR (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id) WHERE r.external_id='{CID}' AND r.resource_id='{old["rid"]}' AND r.content_hash='{old["hash"]}' AND NOT COALESCE(d.data->'mi013_source_enrichments'?'v39',false))<>1
 THEN RAISE EXCEPTION 'signed source count/identity changed'; END IF;
END $guard$;
UPDATE dp_resources SET content_hash='{s["hash"]}',metadata=convert_from(decode('{hexjson(s["meta"])}','hex'),'UTF8')::jsonb,updated_at=now(),last_seen_at=now() WHERE resource_id='{old["rid"]}';
UPDATE dp_records SET data=convert_from(decode('{hexjson(s["data"])}','hex'),'UTF8')::jsonb,metadata=convert_from(decode('{hexjson(s["rmeta"])}','hex'),'UTF8')::jsonb,revision=revision+1,updated_at=now() WHERE resource_id='{old["rid"]}';
DO $guard$ BEGIN
 IF (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>104
 OR (SELECT count(*) FROM dp_resources WHERE collection_id<>'{COLLECTION}')<>{before["other_resources"]}
 OR (SELECT count(*) FROM dp_documents)<>{before["all_documents"]}
 OR (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id) WHERE r.external_id='{CID}' AND r.content_hash='{s["hash"]}' AND d.data->'mi013_source_enrichments'->'v39'->'verified_primary'->'participants'->0->>'inn'='7720494275')<>1
 THEN RAISE EXCEPTION 'v39 award postcommit validation failed'; END IF;
END $guard$;
COMMIT;
SELECT 'V39_DONE='||count(*) FROM dp_resources WHERE collection_id='{COLLECTION}';
"""
    x=query(sql,timeout=105)
    if "V39_DONE=104" not in x:raise RuntimeError("v39 commit receipt missing")

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--apply",action="store_true")
    a.add_argument("--approved-command")
    a.add_argument("--backup-directory",type=Path)
    opts=a.parse_args()
    p=proof();before=snapshot()
    if before["resources"]!=104 or before["records"]!=104:raise RuntimeError("v38 104 source baseline lost")
    old=fetch();new=stage(p,old)
    print(json.dumps({"version":"v39","case":CID,"already":new["done"],"sha":new["hash"],"sources":104},ensure_ascii=False),flush=True)
    if new["done"] or not opts.apply:return
    if opts.approved_command!=ACK or opts.backup_directory is None:raise RuntimeError("need approved backed-up batch")
    b=backup(opts.backup_directory)
    print(json.dumps({"verified_backup":b},ensure_ascii=False),flush=True)
    atomic_write(old,new,before)
    after=snapshot()
    if not stage(p,fetch())["done"] or after["resources"]!=104 or after["records"]!=104 or after["unique_ids"]!=104:raise RuntimeError("v39 independent read-back error")
    if any(after[k]!=before[k] for k in ("other_resources","other_records","all_documents")):raise RuntimeError("unrelated collection changed")
    print(json.dumps({"result":"PASS","backup":b,"after":after},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
