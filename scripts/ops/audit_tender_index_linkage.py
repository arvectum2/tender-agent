"""Read-only exact reconciliation of current local tender chunks to DP.
Historical collections are counted separately; never match by filename or similarity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict

from scripts.ops.repair_legacy_tender_index import read_query
from src.tender_research.rag.presets import (
    legacy_tender_collection_id,
    tender_collection_id,
)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def reconcile(local, platform, collections):
    groups=defaultdict(list)
    for tender,number,cid,did,hash_,text in local:
        groups[(tender,number)].append((cid,did,hash_,text))
    index=defaultdict(list)
    for collection,uri,doc,chunk,hash_,text,count,valid in platform:
        index[(collection,uri)].append((doc,chunk,hash_,text,count,valid))
    known={r[2] for r in local}
    reports=[]
    for (tender,number),chunks in sorted(groups.items()):
        revision=sha("\n".join(f"{cid}:{hash_}" for cid,_,hash_,_ in sorted(chunks)))[:16]
        canonical=tender_collection_id(tender,revision)
        legacy=legacy_tender_collection_id(tender,revision)
        collection=canonical if canonical in collections else legacy
        matched=0
        for cid,did,hash_,text in chunks:
            normalized=" ".join(text.split())
            rows=index.get((collection,"tender-chunk://"+cid),[])
            if len(rows)==1:
                doc,chunk,h,value,count,valid=rows[0]
                if doc and chunk and did and hash_==sha(text) and h==sha(normalized) and value==normalized and count==valid==1:
                    matched+=1
        reports.append({"registry_number":number,"expected":len(chunks),"verified":matched,
                        "canonical":collection==canonical})
    return {"local_chunks":len(local),"verified":sum(r["verified"] for r in reports),
            "missing_or_mismatch":sum(r["expected"]-r["verified"] for r in reports),
            "tenders_with_chunks":len(reports),"complete_tenders":sum(r["expected"]==r["verified"] for r in reports),
            "historical_uri_rows_without_current_local_id":sum(row[1].removeprefix("tender-chunk://") not in known for row in platform),
            "tenders":reports}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--require-complete",action="store_true")
    args=p.parse_args()
    local=read_query("arvectum","""select json_build_array(t.id,t.registry_number,c.id,d.id,c.text_hash,c.text)
        from procurement_document_chunks c join procurement_tender_documents d on d.id=c.document_id and d.tender_id=c.tender_id
        join procurement_tenders t on t.id=c.tender_id order by t.id,c.id""")
    platform=read_query("arvectum_data","""select json_build_array(r.collection_id,r.canonical_uri,d.document_id,c.chunk_id,c.content_hash,c.text,count(e.embedding_id),
        count(e.embedding_id) filter (where e.provider=k.embedding_provider and e.model=k.embedding_model and e.dimension=k.embedding_dimension and e.vector is not null))
        from dp_resources r join dp_collections k using(collection_id)
        left join dp_documents d using(resource_id) left join dp_chunks c using(document_id)
        left join dp_chunk_embeddings e using(chunk_id) where r.canonical_uri like 'tender-chunk://%'
        group by r.collection_id,r.canonical_uri,d.document_id,c.chunk_id,c.content_hash,c.text""")
    collections={r[0] for r in read_query("arvectum_data","select json_build_array(collection_id) from dp_collections")}
    report=reconcile(local,platform,collections)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if args.require_complete and report["missing_or_mismatch"]:
        raise SystemExit(2)


if __name__=="__main__":
    main()
