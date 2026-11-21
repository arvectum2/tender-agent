"""Negative guards for saved SIBUR DP/embedding evidence, without live DB calls."""

import hashlib
import json

import pytest

from scripts.research import reconciled_sibur_index as review


def _saved(tmp_path):
    raw = b"archived spreadsheet source bytes"
    sha = hashlib.sha256(raw).hexdigest()
    name = sha + ".xlsx"
    (tmp_path / name).write_bytes(raw)
    record = {
        "canonical_uri": "content-sha256://" + sha,
        "resource_id": "res-001", "document_id": "doc-001",
        "extraction_status": "extracted", "chunks": 2, "embeddings": 2,
        "matched_embeddings": 2, "matched_chunk_ids": 2,
        "chunk_ids": ["c1", "c2"],
    }
    evidence = {
        "collection_id": review.COLLECTION,
        "provider": "llama_cpp", "model": "Qwen3-Embedding-4B",
        "dimension": 2560, "documents": [record],
    }
    proof_path = tmp_path / "dp-readonly-reconciliation-20261115-0739.json"
    proof_path.write_text(json.dumps(evidence))
    manifest_path = tmp_path / review.MANIFEST
    manifest = {
        "schema": "sibur_dp_readonly_reconciliation_v1",
        "collection_id": review.COLLECTION,
        "evidence_file": proof_path.name,
        "evidence_sha256": hashlib.sha256(proof_path.read_bytes()).hexdigest(),
        "reconciled_sources": [{"sha256": sha, "original_file": name}],
    }
    manifest_path.write_text(json.dumps(manifest))
    return sha, proof_path, evidence, manifest_path, manifest


def test_good_historical_proof_is_not_live_db_evidence(tmp_path):
    sha, _, _, _, _ = _saved(tmp_path)
    result = review.load(tmp_path)
    assert len(result) == 1 and result[sha]["chunks"] == 2
    assert result[sha]["verification"] == review.VERIFICATION


def test_manifest_duplicate_json_keys_not_silently_accepted(tmp_path):
    _, _, _, path, _ = _saved(tmp_path)
    path.write_text(path.read_text().replace('{"schema":', '{"schema":"forged","schema":'))
    with pytest.raises(ValueError, match="duplicate DP receipt JSON field"):
        review.load(tmp_path)


def test_original_byte_tampering_fails(tmp_path):
    sha, _, _, _, _ = _saved(tmp_path)
    (tmp_path / (sha + ".xlsx")).write_bytes(b"different source")
    with pytest.raises(ValueError, match="original source mismatch"):
        review.load(tmp_path)


def test_original_symlink_cannot_bypass_original_hash(tmp_path):
    sha, _, _, _, _ = _saved(tmp_path)
    source = tmp_path / (sha + ".xlsx")
    source.unlink()
    source.symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="linked"):
        review.load(tmp_path)


def test_traversal_original_name_rejected(tmp_path):
    _, _, _, path, manifest = _saved(tmp_path)
    manifest["reconciled_sources"][0]["original_file"] = "../outside.xlsx"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsafe historical source filename"):
        review.load(tmp_path)


def test_duplicate_source_rows_rejected(tmp_path):
    _, _, _, path, manifest = _saved(tmp_path)
    manifest["reconciled_sources"].append(dict(manifest["reconciled_sources"][0]))
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="original source mismatch"):
        review.load(tmp_path)


def test_wrong_embedding_configuration_rejected(tmp_path):
    _, proof, evidence, path, manifest = _saved(tmp_path)
    evidence["dimension"] = 768
    proof.write_text(json.dumps(evidence))
    manifest["evidence_sha256"] = hashlib.sha256(proof.read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="embedding configuration"):
        review.load(tmp_path)


def test_boolean_chunk_count_is_not_valid_evidence(tmp_path):
    _, proof, evidence, path, manifest = _saved(tmp_path)
    evidence["documents"][0]["chunks"] = True
    proof.write_text(json.dumps(evidence))
    manifest["evidence_sha256"] = hashlib.sha256(proof.read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="embedding coverage"):
        review.load(tmp_path)


def test_incomplete_prior_evidence_does_not_claim_historical_verified(tmp_path):
    _, _, _, path, manifest = _saved(tmp_path)
    manifest["reconciled_sources"][0]["prior_evidence_file"] = "dp-readonly-reconciliation-20261115-0739.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="incomplete prior attestation"):
        review.load(tmp_path)


def test_nonexistent_manifest_rejected_not_empty_success(tmp_path):
    with pytest.raises(ValueError, match="missing, linked"):
        review.load(tmp_path)


def test_cli_reports_offline_status_only(tmp_path, monkeypatch, capsys):
    _saved(tmp_path)
    monkeypatch.setattr("sys.argv", ["reconcile", "--saved-evidence", str(tmp_path)])
    review.main()
    report = json.loads(capsys.readouterr().out)
    assert report == {
        "status": "historical_saved_DP_receipts_verified",
        "source_original_files": 1,
        "matching_chunk_and_embedding_records": 2,
        "source_url_membership_verified_by_this_helper": False,
        "current_live_DP_verified": False,
        "network_requests": 0,
        "database_mutations": 0,
    }
