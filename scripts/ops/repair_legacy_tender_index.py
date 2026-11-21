"""Bounded six-tender historical index repair. Plan is read-only by default.

No source revision assertion, no SQL writes, no deletion, no DP/TA deployment.
Apply uses existing Data Platform ingest API and the required MI backup/gate.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.tender_research.config import load_config
from src.tender_research.rag.data_platform import (
    build_data_platform_client,
    complete_index_counts,
    validate_chunk_ingest_receipt,
)
from src.tender_research.rag.presets import (
    legacy_tender_collection_id,
    tender_collection_id,
)

ROOT = Path("/Volumes/ArvectumSSD/Archives/legacy-mac/Arvectum-local-archive-pre-2026-08-01/Arvectum/archives/legacy-data/fbe780220b7acf9e")
EXPECTED = {"0318300120826000339":57,"0323100010326000013":47,"0587600003926000036":85,
            "0373200027426001278":3,"0321300096826000140":85,"0373200027426001279":3}
MI = Path("/Users/master/ArvectumSafe/worktrees/tender-agent-mi")
PYTHON = "/Users/master/ArvectumSafe/.venvs/tender-agent-mi/bin/python"
RUN = Path("/Users/master/ArvectumSafe/runtime/ta-source-discovery-20261114/autonomous-runner")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))+"\n").encode()


def norm(text):
    return " ".join(text.split())


def read_query(db, sql):
    out = subprocess.check_output(["docker","exec","arvectum-postgres","psql","-X","-qAt","-U","arvectum","-d",db,
                                   "-v","ON_ERROR_STOP=1","-c","BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; "+sql+"; ROLLBACK;"],text=True,timeout=60)
    return [json.loads(x) for x in out.splitlines()]


def archive_path(relative):
    if not isinstance(relative,str) or not relative.startswith("data/"):
        raise ValueError("unexpected historical path")
    candidate = ROOT / relative.removeprefix("data/")
    if candidate.is_symlink() or not candidate.is_file() or not candidate.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("invalid archived original path")
    if candidate.stat().st_size > 25*1024*1024:
        raise ValueError("original bound exceeded")
    return candidate


def source_plan():
    numbers=",".join("'"+n+"'" for n in EXPECTED)
    rows=read_query("arvectum",f"""select json_build_array(t.registry_number,t.id,d.id,d.file_name,d.local_path,d.sha256,d.extracted_text_path,c.id,c.text_hash,c.text,c.raw_meta->>'source') from procurement_document_chunks c join procurement_tender_documents d on d.id=c.document_id and d.tender_id=c.tender_id join procurement_tenders t on t.id=c.tender_id where t.registry_number in ({numbers}) order by t.id,c.id""")
    by=defaultdict(list); docs={}; texts={}; chunk_data={}
    for number,tid,did,name,original,sha,extracted,cid,h,text,source in rows:
        if source!="extracted_text" or h!=digest(text.encode()) or not text.strip():
            raise ValueError("historical chunk/source mismatch")
        if did not in docs:
            p,z=archive_path(original),archive_path(extracted)
            if digest(p.read_bytes())!=sha:
                raise ValueError("original hash mismatch")
            raw=z.read_bytes();texts[did]=norm(raw.decode("utf8"))
            docs[did]={"document_id":did,"tender_id":tid,"original":str(p),"original_sha256":sha,
                       "extracted":str(z),"extracted_sha256":digest(raw)}
        if norm(text) not in texts[did]:
            raise ValueError("stored chunk missing from archived extracted text")
        if cid in chunk_data:
            raise ValueError("duplicate chunk")
        record={"chunk_id":cid,"document_id":did,"text_hash":h,"normalized_sha256":digest(norm(text).encode())}
        by[(number,tid)].append(record);chunk_data[cid]=(name,text)
    if {n:len(v) for (n,_),v in by.items()}!=EXPECTED or len(docs)!=14:
        raise ValueError("exact six-tender repair scope drifted")
    tenders=[]
    for (n,tid),chunks in sorted(by.items()):
        revision=digest("\n".join(c["chunk_id"]+":"+c["text_hash"] for c in chunks).encode())[:16]
        tenders.append({"registry_number":n,"tender_id":tid,"collection_id":tender_collection_id(tid,revision),
                        "legacy_collection_id":legacy_tender_collection_id(tid,revision),"chunks":chunks})
    return {"schema":"arvectum.tender.legacy-index-repair/1","documents":sorted(docs.values(),key=lambda x:x["document_id"]),
            "tenders":tenders,"historical_only":True,"source_revision_current":False},chunk_data


def inspect_existing(plan):
    expected={t["collection_id"]:{c["chunk_id"]:c for c in t["chunks"]} for t in plan["tenders"]}
    ids=[t[k] for t in plan["tenders"] for k in ("collection_id","legacy_collection_id")]
    quoted=",".join("'"+s+"'" for s in ids)
    rows=read_query("arvectum_data",f"""select json_build_array(r.collection_id,r.canonical_uri,d.document_id,c.chunk_id,c.content_hash,count(e.embedding_id)) from dp_resources r left join dp_documents d using(resource_id) left join dp_chunks c using(document_id) left join dp_chunk_embeddings e using(chunk_id) where r.collection_id in ({quoted}) group by r.collection_id,r.canonical_uri,d.document_id,c.chunk_id,c.content_hash""")
    collections=read_query("arvectum_data",f"""select json_build_array(collection_id,owner,name,embedding_model,embedding_dimension) from dp_collections where collection_id in ({quoted})""")
    names={t["collection_id"]:"Tender "+t["registry_number"] for t in plan["tenders"]}
    for cid,owner,name,model,dimension in collections:
        if cid not in names or owner!="tender-agent" or name!=names[cid] or model not in (None,"Qwen3-Embedding-4B") or dimension not in (None,2560):
            raise ValueError("conflicting collection contract")
    present=set()
    for collection,uri,doc,chunk,h,vectors in rows:
        local=uri.removeprefix("tender-chunk://")
        identity=(collection,local)
        if (collection not in expected or local not in expected[collection] or uri!="tender-chunk://"+local
                or identity in present or not doc or not chunk or vectors!=1
                or h!=expected[collection][local]["normalized_sha256"]):
            raise ValueError("foreign, incomplete or conflicting index resource; do not overwrite")
        present.add(identity)
    return present


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--apply",action="store_true")
    p.add_argument("--expected-plan-sha256")
    args=p.parse_args()
    plan,data=source_plan()
    raw=canonical(plan); fingerprint=digest(raw)
    present=inspect_existing(plan)
    if not args.apply:
        with args.plan.open("xb") as f:
            f.write(raw)
        args.plan.chmod(0o600)
        print(json.dumps({"status":"READ_ONLY_PLAN","sha256":fingerprint,"tenders":len(plan["tenders"]),
                          "documents":len(plan["documents"]),"chunks":len(data),"already_linked":len(present)}))
        return
    if args.expected_plan_sha256!=fingerprint or args.plan.read_bytes()!=raw:
        raise ValueError("approved plan no longer matches current data")
    apply_plan(plan,data,args.plan)


def apply_plan(plan,data,plan_path):
    # Production writes are a separate, explicitly authorized action.
    os.umask(0o077)
    with (RUN/"mutation.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        live,_=source_plan()
        if live!=plan:
            raise ValueError("source changed before repair")
        present=inspect_existing(plan)
        if len(present)==len(data):
            print("ALREADY_COMPLETE",flush=True)
            return
        subprocess.run([PYTHON,"-m","scripts.market_intelligence.backup_pq_postgres"],cwd=MI,
                       check=True,stdout=subprocess.DEVNULL,timeout=300)
        gate=json.loads(subprocess.check_output([PYTHON,"-m","scripts.market_intelligence.verify_internal_runtime"],cwd=MI,timeout=180))
        stamp=datetime.fromisoformat(gate["verified_at_utc"])
        if (gate.get("status")!="pass" or gate.get("postgresql_mutated_by_preflight") is not False
                or gate.get("postgresql",{}).get("database")!="arvectum_data"
                or not gate.get("backup",{}).get("sha256") or not timedelta(0)<=datetime.now(UTC)-stamp<=timedelta(minutes=45)):
            raise ValueError("fresh canonical prewrite gate required")
        receipt=plan_path.with_name(plan_path.name+".apply.jsonl")
        def record(value):
            with receipt.open("a") as f:
                f.write(json.dumps(value,ensure_ascii=False)+"\n")
                f.flush();os.fsync(f.fileno())
        record({"status":"PREWRITE_GATE_PASS","plan_sha256":digest(canonical(plan)),
                "backup_sha256":gate["backup"]["sha256"],"initial_linked":len(present)})
        config=load_config()
        if str(config.rag_data_platform_base_url).rstrip("/")!="http://127.0.0.1:8094":
            raise ValueError("unexpected live Data Platform endpoint")
        if source_plan()[0]!=plan or inspect_existing(plan)!=present:
            raise ValueError("state changed after gate")
        with build_data_platform_client(config) as client:
            for tender in plan["tenders"]:
                cid=tender["collection_id"]
                client.ensure_collection(collection_id=cid,name="Tender "+tender["registry_number"])
                for chunk in tender["chunks"]:
                    local=chunk["chunk_id"]
                    if (cid,local) in present:
                        continue
                    if datetime.now(UTC)-stamp>timedelta(minutes=45):
                        raise ValueError("prewrite gate expired; reconcile before continuation")
                    name,text=data[local]
                    result=client.ingest_chunk(collection_id=cid,chunk_id=local,file_name=name,text=text)
                    validate_chunk_ingest_receipt(result,cid,local)
                    record({"status":"INGEST_RECEIPT","collection_id":cid,"chunk_id":local,
                            "resource_id":result["resource_id"],"document_id":result["document_id"]})
                if not complete_index_counts(client.collection_stats(cid),len(tender["chunks"])):
                    raise ValueError("collection count mismatch")
                print("COLLECTION_COUNTS_PASS",tender["registry_number"],len(tender["chunks"]),flush=True)
        if source_plan()[0]!=plan or len(inspect_existing(plan))!=len(data):
            raise ValueError("exact live source/linkage verification failed")
        record({"status":"HISTORICAL_INDEX_REPAIR_PASS","linked":len(data),"current_revision_attested":False})
        print("HISTORICAL_INDEX_REPAIR_PASS",len(data),flush=True)


if __name__=="__main__":
    main()
