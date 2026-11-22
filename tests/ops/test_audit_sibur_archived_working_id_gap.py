"""Synthetic source/working ID-difference tests; no real DB or 4k pages."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from scripts.research import audit_sibur_archived_working_id_gap as mod


def saved_gap():
    original = {"a", "b"}
    db = {"b", "c"}
    return {
        "archived_unique_ids": len(original),
        "working_unique_source_ids": len(db),
        "missing_from_working": 1,
        "working_not_in_archive": 1,
        "overlapping_ids": 1,
        "source_archive_unique_ids_sha256": mod.digest_ids(original),
        "working_database_ids_sha256": mod.digest_ids(db),
        "missing_historical_ids_sha256": mod.digest_ids({"a"}),
        "work_database_cluster_identifier": mod.EXPECTED_CLUSTER,
        "categories": {"107": {"missing_in_working": 1}},
    }


def test_exact_member_counts_and_newline_final_digests():
    old = saved_gap()
    report = mod.summarize_gap({"107": {"a", "b"}}, {"b", "c"}, old)
    assert report["status"] == "PASS_HISTORICAL_IDENTITY_DIFF_ONLY"
    assert report["missing_historical"] == report["working_only"] == 1
    assert report["overlap"] == 1
    assert report["mass_import_authorized"] is False
    assert report["gap_root_cause"] == "UNKNOWN"
    assert report["production_mutations"] == 0


@pytest.mark.parametrize("field", [
    "archived_unique_ids", "working_unique_source_ids", "missing_from_working",
    "overlapping_ids", "working_not_in_archive", "missing_historical_ids_sha256",
])
def test_any_saved_gap_change_fails_closed(field):
    old = saved_gap()
    old[field] = old[field] + 1 if isinstance(old[field], int) else "a" * 64
    with pytest.raises(mod.GapEvidenceError):
        mod.summarize_gap({"107": {"a", "b"}}, {"b", "c"}, old)


def test_pg16_read_only_sql_is_only_allowed_working_query(monkeypatch):
    calls = []

    def fake_run(command, **kw):
        calls.append((command, kw))
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "sid": mod.EXPECTED_CLUSTER, "readonly": "on", "ids": ["b", "c"],
        })+"\n", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    assert mod.working_id_snapshot(saved_gap()) == {"b", "c"}
    argv, opts = calls[0]
    assert argv[:3] == ["docker", "exec", "arvectum-local-e2e-db-1"]
    assert "arvectum_local" in argv and "arvectum" in argv
    assert "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY" in argv[-1]
    assert "procurement_tenders" in argv[-1] and "source='sibur_public'" in argv[-1]
    assert opts["check"] is False and opts["timeout"] == 40


@pytest.mark.parametrize("readonly,identifier", [("off", mod.EXPECTED_CLUSTER), ("on", "wrong")])
def test_wrong_cluster_or_write_access_never_accepted(monkeypatch, readonly, identifier):
    def fake_run(*args, **kw):
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "sid": identifier, "readonly": readonly, "ids": ["b", "c"],
        }) + "\n", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    with pytest.raises(mod.GapEvidenceError, match="wrong_working_cluster_or_not_readonly"):
        mod.working_id_snapshot(saved_gap())


def test_private_receipt_created_once_and_source_read_guard(tmp_path):
    doc = tmp_path/"receipt.json"
    proof = {"status": "PASS_HISTORICAL_IDENTITY_DIFF_ONLY"}
    mod.proof_create_once(doc, proof)
    assert json.loads(doc.read_text()) == proof
    assert (doc.stat().st_mode & 0o777) == 0o600
    with pytest.raises(mod.GapEvidenceError, match="proof_destination_untrusted_or_exists"):
        mod.proof_create_once(doc, {"status": "FORGED"})
    sha = hashlib.sha256(doc.read_bytes()).hexdigest()
    assert mod.read_receipt(doc, sha) == proof
    with pytest.raises(mod.GapEvidenceError, match="saved_receipt_sha_changed"):
        mod.read_receipt(doc, "0" * 64)
    assert doc.read_bytes()
