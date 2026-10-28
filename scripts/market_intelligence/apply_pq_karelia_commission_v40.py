"""MI-013 v40: original EIS 35kV UKRM mixed multi-substation EPC commission.
Only enriches one existing original notice; no signed hardware award or invented OEM.
Requires verified original backup before atomic PostgreSQL commit.
"""
import argparse,copy,hashlib,json
from pathlib import Path
from import_pq_postgres_v29 import DATA,COLLECTION,SOURCE,backup,query,snapshot
CID="223fz:32616433248:lot1"
FILE="original_karelia_35kv_commission_20261028.v40.json"
ACK="MI013-V40-KARELIA-EPC-20261028"

def proof():
    x=json.loads((DATA/FILE).read_text(encoding="utf8"))
    p=x["patches"][0]
    if (x["new_procurement_notices"]!=0 or x["existing_cases_enriched"]!=1
        or x["new_original_registered_signed_contracts"]!=0 or len(x["patches"])!=1):
        raise ValueError("v40 one existing mixed EPC case, zero signed deals")
    f=p["final_protocol"];pr=p["preliminary_protocol"];q=p["equipment"]
    if (p["canonical_id"]!=CID or p["procedure_id"]!="32616433248"
        or p["source_grade"]!="first_party_EIS_223_original_final_and_qualification_attachments_sha_verified"
        or f["signed_date"]!="2026-10-19" or pr["signed_date"]!="2026-10-14"
        or f["bids_received"]!=1 or pr["qualified_bids"]!=1
        or not f["procurement_legally_failed_one_bid"] or f["retender_price_reduced"]
        or f["bid_1_price_rub"]!="56330673.93"
        or p["full_epc_total_nmc_rub"]!="56330673.93"
        or not p["full_epc_cost_is_not_ukrm_price"]
        or q["units_requested"]!=1 or q["site_bus_voltage_kv"]!=35
        or q["hardware_only_signed_price_rub"] is not None
        or f["original_archive"]["sha256"]!="98062c8f6bb47d177c7630374a8f57193dcf4177e7fd37f3204cf140de05de4e"
        or pr["original_archive"]["sha256"]!="842c06f3d0944e8266fd2aefaeb538ab04b19a5195fe91172fbad923684ad861"
        or p["second_tier_bidder"]["verified_primary_legal_person"]
        or p["signed_original_rd223_contract_verified"]):
        raise ValueError("original commission or source grade discrepancy")
    return p

def fetch():
    rid=hashlib.sha256(CID.encode("utf8")).hexdigest()[:48]
    row=query(f"SELECT jsonb_build_object('rid',r.resource_id,'cid',r.external_id,'hash',r.content_hash,'meta',r.metadata,'data',d.data,'rmeta',d.metadata,'revision',d.revision)::text FROM dp_resources r JOIN dp_records d USING(resource_id) WHERE r.collection_id='{COLLECTION}' AND r.resource_id='{rid}' AND r.external_id='{CID}';")
    if not row:raise RuntimeError("registered 104th original source case absent")
    return json.loads(row)

def stage(p,old):
    d=copy.deepcopy(old["data"])
    if (d.get("canonical_id")!=CID or d.get("status") is None
        or d.get("registry_contract",{}).get("signed_contract_registry_verified") is True):
        raise ValueError("wrong pre-existing non-signed EPC source")
    if "v40" in d.get("mi013_source_enrichments",{}):
        if d["mi013_source_enrichments"]["v40"]["verified_primary"]!=p:
            raise ValueError("v40 already present with a different original archive")
        h=hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if old["hash"]!=h:raise ValueError("existing source hash mismatch")
        return {"done":True,"hash":h}
    if old["meta"]["data_version"]!="v29":
        raise ValueError("baseline modified, refuse to overwrite another research pass")
    d.setdefault("mi013_source_enrichments",{})["v40"]={
        "source_file":FILE,"verified_primary":copy.deepcopy(p),
        "source_grade":"original_EIS_35kv_turnkey_EPC_commission_two_archive"}
    h=hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    m=copy.deepcopy(old["meta"])
    m.update({"data_version":"v40","mi013_import_batch":"v40-20261028",
        "source_evidence_versions":sorted(d["mi013_source_enrichments"])})
    m["source_urls"]=list(dict.fromkeys(m["source_urls"]+[p["preliminary_protocol"]["original_archive"]["url"],p["final_protocol"]["original_archive"]["url"]]))
    rm=copy.deepcopy(old["rmeta"])
    rm.update({"research_version":"v40","source_content_hash":h,"source_evidence_urls":m["source_urls"]})
    return {"done":False,"hash":h,"data":d,"meta":m,"rmeta":rm}

def atomic_write(old,s,before):
    def hexjson(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode().hex()
    sql=f"""
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='90s';
SELECT pg_advisory_xact_lock(hashtext('mi013-v40-karelia-original-35kv-epc'));
DO $guard$ BEGIN
 IF current_database()<>'arvectum_data'
 OR (SELECT owner FROM dp_collections WHERE collection_id='{COLLECTION}')<>'tender-agent'
 OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>104
 OR (SELECT count(*) FROM dp_records WHERE resource_id IN (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>104
 OR (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id) WHERE r.external_id='{CID}' AND r.resource_id='{old["rid"]}' AND r.content_hash='{old["hash"]}' AND NOT COALESCE(d.data->'mi013_source_enrichments'?'v40',false))<>1
 THEN RAISE EXCEPTION 'non-signed EPC source count/identity changed'; END IF;
END $guard$;
UPDATE dp_resources SET content_hash='{s["hash"]}',metadata=convert_from(decode('{hexjson(s["meta"])}','hex'),'UTF8')::jsonb,updated_at=now(),last_seen_at=now() WHERE resource_id='{old["rid"]}';
UPDATE dp_records SET data=convert_from(decode('{hexjson(s["data"])}','hex'),'UTF8')::jsonb,metadata=convert_from(decode('{hexjson(s["rmeta"])}','hex'),'UTF8')::jsonb,revision=revision+1,updated_at=now() WHERE resource_id='{old["rid"]}';
DO $guard$ BEGIN
 IF (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>104
 OR (SELECT count(*) FROM dp_resources WHERE collection_id<>'{COLLECTION}')<>{before["other_resources"]}
 OR (SELECT count(*) FROM dp_documents)<>{before["all_documents"]}
 OR (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id) WHERE r.external_id='{CID}' AND r.content_hash='{s["hash"]}' AND d.data->'mi013_source_enrichments'->'v40'->'verified_primary'->'final_protocol'->>'bid_1_price_rub'='56330673.93')<>1
 THEN RAISE EXCEPTION 'v40 award postcommit validation failed'; END IF;
END $guard$;
COMMIT;
SELECT 'V40_DONE='||count(*) FROM dp_resources WHERE collection_id='{COLLECTION}';
"""
    x=query(sql,timeout=105)
    if "V40_DONE=104" not in x:raise RuntimeError("v40 commit receipt missing")

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--apply",action="store_true")
    a.add_argument("--approved-command")
    a.add_argument("--backup-directory",type=Path)
    opts=a.parse_args()
    p=proof();before=snapshot()
    if before["resources"]!=104 or before["records"]!=104:raise RuntimeError("v38 104 source baseline lost")
    old=fetch();new=stage(p,old)
    print(json.dumps({"version":"v40","case":CID,"already":new["done"],"sha":new["hash"],"sources":104},ensure_ascii=False),flush=True)
    if new["done"] or not opts.apply:return
    if opts.approved_command!=ACK or opts.backup_directory is None:raise RuntimeError("need approved backed-up batch")
    b=backup(opts.backup_directory)
    print(json.dumps({"verified_backup":b},ensure_ascii=False),flush=True)
    atomic_write(old,new,before)
    after=snapshot()
    if not stage(p,fetch())["done"] or after["resources"]!=104 or after["records"]!=104 or after["unique_ids"]!=104:raise RuntimeError("v40 independent read-back error")
    if any(after[k]!=before[k] for k in ("other_resources","other_records","all_documents")):raise RuntimeError("unrelated collection changed")
    print(json.dumps({"result":"PASS","backup":b,"after":after},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
