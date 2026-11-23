"""Distinguish exact read-only PostgreSQL evidence from original HTTP ingest receipts."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

COLLECTION="tender-agent:sibur-public-research"
MANIFEST="dp-reconciled-resources-v1.json"
VERIFICATION="READ_ONLY_POSTGRESQL_RESOURCE_CHUNK_EMBEDDING_VERIFIED"
MAX_EVIDENCE_BYTES=16*1024*1024
MAX_SOURCE_BYTES=25*1024*1024


def _unique_keys(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("duplicate DP receipt JSON field")
        result[key]=value
    return result


def _checked_file(directory,name,limit):
    if not isinstance(name,str) or not name or Path(name).name!=name or "\\" in name:
        raise ValueError("unsafe historical source filename")
    p=directory/name
    if p.parent!=directory or p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=limit:
        raise ValueError("missing, linked or oversized historical source evidence")
    return p



def sha256(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


def read_evidence(directory, name, digest):
    if (not isinstance(name,str) or not re.fullmatch(r"dp-readonly-reconciliation-[0-9-]+\.json",name)
            or not isinstance(digest,str) or not re.fullmatch(r"[0-9a-f]{64}",digest)):
        raise ValueError("unexpected evidence file")
    p=_checked_file(directory,name,MAX_EVIDENCE_BYTES)
    if sha256(p)!=digest:
        raise ValueError("reconciled DB evidence hash mismatch")
    evidence=json.loads(p.read_bytes(),object_pairs_hook=_unique_keys)
    if (evidence.get("collection_id")!=COLLECTION or evidence.get("provider")!="llama_cpp"
            or evidence.get("model")!="Qwen3-Embedding-4B" or evidence.get("dimension")!=2560):
        raise ValueError("unexpected collection or embedding configuration")
    by={}
    for row in evidence["documents"]:
        uri=row["canonical_uri"]
        if uri in by or not re.fullmatch(r"content-sha256://[0-9a-f]{64}",uri):
            raise ValueError("invalid or duplicate resource identity")
        by[uri]=row
    return evidence,by


def load(directory):
    manifest=directory/MANIFEST
    if not directory.is_dir() or directory.is_symlink() or directory.resolve()!=directory:
        raise ValueError("unsafe historical DP directory")
    manifest=_checked_file(directory,MANIFEST,1*1024*1024)
    m=json.loads(manifest.read_bytes(),object_pairs_hook=_unique_keys)
    if (not isinstance(m,dict) or m.get("schema")!="sibur_dp_readonly_reconciliation_v1"
            or m.get("collection_id")!=COLLECTION or not isinstance(m.get("reconciled_sources"),list)
            or not 0<len(m["reconciled_sources"])<=10000):
        raise ValueError("unexpected reconciliation manifest")
    evidence,by=read_evidence(directory,m["evidence_file"],m["evidence_sha256"])
    prior_cache={}
    result={}
    for item in m["reconciled_sources"]:
        if not isinstance(item,dict):
            raise TypeError("invalid original source member")
        sha=item["sha256"]
        if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{64}",sha) or sha in result:
            raise ValueError("recovered original source mismatch")
        original=_checked_file(directory,item["original_file"],MAX_SOURCE_BYTES)
        if original.stem!=sha or sha256(original)!=sha:
            raise ValueError("recovered original source mismatch")
        uri="content-sha256://"+sha
        if uri not in by:
            raise ValueError("original source missing from DP evidence")
        d=by[uri];n=d["chunks"]
        # Preserve the original attestation identity when a later full collection
        # snapshot confirms the same resource and every chunk/embedding identity.
        proof_hash=m["evidence_sha256"]
        if "prior_evidence_file" in item or "prior_evidence_sha256" in item:
            if not all(k in item for k in ("prior_evidence_file","prior_evidence_sha256")):
                raise ValueError("incomplete prior attestation")
            key=(item["prior_evidence_file"],item["prior_evidence_sha256"])
            if key not in prior_cache:
                prior_cache[key]=read_evidence(directory,*key)[1]
            prior=prior_cache[key].get(uri)
            if prior is None or not isinstance(prior.get("chunk_ids"),list) or not isinstance(d.get("chunk_ids"),list):
                raise ValueError("prior resource attestation differs from current evidence")
            normalize=lambda row: {**row,"chunk_ids":sorted(row["chunk_ids"])}
            if prior is None or normalize(prior)!=normalize(d):
                raise ValueError("prior resource attestation differs from current evidence")
            proof_hash=key[1]
        if (d["extraction_status"]!="extracted" or type(n) is not int or n<=0
                or not isinstance(d.get("chunk_ids"),list)
                or type(d.get("embeddings")) is not int
                or type(d.get("matched_embeddings")) is not int
                or type(d.get("matched_chunk_ids")) is not int
                or n!=d["embeddings"] or n!=d["matched_embeddings"] or n!=d["matched_chunk_ids"]
                or n!=len(d["chunk_ids"]) or n!=len(set(d["chunk_ids"]))):
            raise ValueError("recovered embedding coverage mismatch")
        result[sha]={"collection_id":COLLECTION,"canonical_uri":uri,
                     "resource_id":d["resource_id"],"document_id":d["document_id"],
                     "chunks":n,"embeddings":n,"extraction_status":"extracted","verification":VERIFICATION,
                     "source_db_evidence_sha256":proof_hash,
                     "embedding_provider":evidence["provider"],"embedding_model":evidence["model"],
                     "embedding_dimension":evidence["dimension"]}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saved-evidence",type=Path,required=True)
    docs=load(parser.parse_args().saved_evidence)
    print(json.dumps({"status":"historical_saved_DP_receipts_verified",
        "source_original_files":len(docs),
        "matching_chunk_and_embedding_records":sum(x["chunks"] for x in docs.values()),
        "source_url_membership_verified_by_this_helper":False,
        "current_live_DP_verified":False,
        "network_requests":0,"database_mutations":0},ensure_ascii=False))


if __name__=="__main__":
    main()
