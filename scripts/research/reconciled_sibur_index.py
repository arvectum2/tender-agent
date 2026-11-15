"""Distinguish exact read-only PostgreSQL evidence from original HTTP ingest receipts."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

COLLECTION="tender-agent:sibur-public-research"
MANIFEST="dp-reconciled-resources-v1.json"
VERIFICATION="READ_ONLY_POSTGRESQL_RESOURCE_CHUNK_EMBEDDING_VERIFIED"


def sha256(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


def read_evidence(directory, name, digest):
    p=directory/name
    if p.parent!=directory or p.is_symlink() or not re.fullmatch(r"dp-readonly-reconciliation-[0-9-]+\.json",name):
        raise ValueError("unexpected evidence file")
    if sha256(p)!=digest:
        raise ValueError("reconciled DB evidence hash mismatch")
    evidence=json.loads(p.read_text())
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
    if not manifest.exists():
        return {}
    m=json.loads(manifest.read_text())
    if m.get("schema")!="sibur_dp_readonly_reconciliation_v1" or m.get("collection_id")!=COLLECTION:
        raise ValueError("unexpected reconciliation manifest")
    evidence,by=read_evidence(directory,m["evidence_file"],m["evidence_sha256"])
    prior_cache={}
    result={}
    for item in m["reconciled_sources"]:
        sha=item["sha256"]
        original=directory/item["original_file"]
        if sha in result or original.parent!=directory or original.is_symlink() or original.stem!=sha or sha256(original)!=sha:
            raise ValueError("recovered original source mismatch")
        uri="content-sha256://"+sha
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
            normalize=lambda row: {**row,"chunk_ids":sorted(row["chunk_ids"])}
            if prior is None or normalize(prior)!=normalize(d):
                raise ValueError("prior resource attestation differs from current evidence")
            proof_hash=key[1]
        if (d["extraction_status"]!="extracted" or type(n) is not int or n<=0
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


if __name__=="__main__":
    print(json.dumps(load(Path(sys.argv[1])),ensure_ascii=False))
