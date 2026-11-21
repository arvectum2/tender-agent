import hashlib
import json

import pytest

from scripts.research.reconciled_sibur_index import COLLECTION, MANIFEST, load


def test_verified_recovery_is_not_fabricated_ingest_and_rejects_tampering(tmp_path):
    data=b"original sample"
    sha=hashlib.sha256(data).hexdigest()
    original=tmp_path/(sha+".xlsx")
    original.write_bytes(data)
    evidence={"collection_id":COLLECTION,"provider":"llama_cpp","model":"Qwen3-Embedding-4B","dimension":2560,
              "documents":[{"canonical_uri":"content-sha256://"+sha,"resource_id":"res","document_id":"doc",
              "extraction_status":"extracted","chunks":2,"embeddings":2,"matched_embeddings":2,
              "matched_chunk_ids":2,"chunk_ids":["a","b"]}]}
    f=tmp_path/"dp-readonly-reconciliation-20261115-0724.json"
    m=tmp_path/MANIFEST
    def write():
        f.write_text(json.dumps(evidence))
        m.write_text(json.dumps({"schema":"sibur_dp_readonly_reconciliation_v1","collection_id":COLLECTION,
                     "evidence_file":f.name,"evidence_sha256":hashlib.sha256(f.read_bytes()).hexdigest(),
                     "reconciled_sources":[{"sha256":sha,"original_file":original.name}]}))
    write()
    result=load(tmp_path)[sha]
    assert result["embeddings"]==2 and "embeddings_written" not in result
    assert result["verification"]=="READ_ONLY_POSTGRESQL_RESOURCE_CHUNK_EMBEDDING_VERIFIED"
    evidence["documents"][0]["matched_chunk_ids"]=1
    write()
    with pytest.raises(ValueError,match="coverage"):
        load(tmp_path)
    f.write_text("tampered")
    with pytest.raises(ValueError,match="hash mismatch"):
        load(tmp_path)


def test_prior_attestation_preserved_only_when_exact_resource_unchanged(tmp_path):
    data=b"old source"
    sha=hashlib.sha256(data).hexdigest()
    original=tmp_path/(sha+".xlsx")
    original.write_bytes(data)
    row={"canonical_uri":"content-sha256://"+sha,"resource_id":"res","document_id":"doc",
         "extraction_status":"extracted","chunks":2,"embeddings":2,"matched_embeddings":2,
         "matched_chunk_ids":2,"chunk_ids":["a","b"]}
    base={"collection_id":COLLECTION,"provider":"llama_cpp","model":"Qwen3-Embedding-4B","dimension":2560}
    old=tmp_path/"dp-readonly-reconciliation-20261115-0724.json"
    new=tmp_path/"dp-readonly-reconciliation-20261115-0739.json"
    old.write_text(json.dumps({**base,"documents":[row]}))
    old_hash=hashlib.sha256(old.read_bytes()).hexdigest()
    def manifest(current):
        new.write_text(json.dumps({**base,"documents":[current]}))
        (tmp_path/MANIFEST).write_text(json.dumps({"schema":"sibur_dp_readonly_reconciliation_v1","collection_id":COLLECTION,
            "evidence_file":new.name,"evidence_sha256":hashlib.sha256(new.read_bytes()).hexdigest(),
            "reconciled_sources":[{"sha256":sha,"original_file":original.name,
            "prior_evidence_file":old.name,"prior_evidence_sha256":old_hash}]}))
    manifest({**row,"chunk_ids":["b","a"]})
    assert load(tmp_path)[sha]["source_db_evidence_sha256"]==old_hash
    manifest({**row,"chunk_ids":["a","different"]})
    with pytest.raises(ValueError,match="attestation differs"):
        load(tmp_path)
    manifest(row)
    old.write_text("tampered")
    with pytest.raises(ValueError,match="hash mismatch"):
        load(tmp_path)
