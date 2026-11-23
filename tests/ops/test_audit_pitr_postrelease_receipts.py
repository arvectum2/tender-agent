"""Fixture-only independent restore-receipt and PG major version safety tests."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.ops.audit_pitr_postrelease_receipts import BackupEvidenceError, audit


def _fixture(root: Path):
    base = root / "base-20261121T131504536797Z" / "data"
    base.mkdir(parents=True)
    (base / "PG_VERSION").write_text("17\n")
    (base / "backup_manifest").write_text('{"Files": []}')
    source = {
        "status": "pass", "live_database_mutated": False,
        "base_path": str(base), "source_system_identifier": "7692004809331994662",
        "manifest_verified": "backup successfully verified",
        "isolated_same_image_restore": {"database": "arvectum_data", "system_identifier": "7692004809331994662"},
    }
    clone = {
        "status": "pass", "production_write": False, "network_none": True,
        "source_mount_readonly": True, "pg_verifybackup_pass": True,
        "integrated_wal_base_verified": True, "source_system_identifier": "7692004809331994662",
        "physical_source_base": base.parent.name,
        "postrelease_business_schema127_physical_restored": True,
        "exact_archived_postbase_restore_target_tested": False,
        "continuous_7day_pitr_proven": False,
        "databases": [
            {"database": "arvectum", "revision": "127_private_review_link_corrections",
             "tenders": 64, "new_tables": 7, "system_identifier": "7692004809331994662", "recovery": False},
            {"database": "arvectum_data", "collections": 73,
             "system_identifier": "7692004809331994662", "recovery": False},
        ],
    }
    p = base.parent / "restore-verified.json"
    q = root / "verified-physical-production-127.json"
    binary = root / "pg_verifybackup"
    binary.write_text("fake_binary_not_executed")
    p.write_text(json.dumps(source))
    q.write_text(json.dumps(clone))
    return p, q, binary, source, clone


def _runner(version="pg_verifybackup (PostgreSQL) 17.12\n", verify_rc=0):
    calls = []

    def run(argv, **kwargs):
        assert kwargs["capture_output"] and kwargs["text"]
        calls.append(argv)
        if argv[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout=version)
        return SimpleNamespace(returncode=verify_rc, stdout="", stderr="signed-url-in-private-error")

    return run, calls


def test_physical_base_receipts_proven_but_no_wal_or_seven_day(tmp_path):
    p, q, binary, _source, _clone = _fixture(tmp_path)
    runner, calls = _runner()
    result = audit(p, q, binary, runner=runner)
    assert result["physical_backup_integrity"] == "VERIFIED"
    assert result["business_revision"] == "127_private_review_link_corrections"
    assert result["dp_collections"] == 73
    assert result["continuous_seven_day_pitr"] == "NOT_PROVEN"
    assert result["archived_postbase_exact_wal_target"] == "NOT_PROVEN"
    assert result["production_recovery_acceptance"] == "BLOCKED"
    assert len(calls) == 2 and calls[1][-2] == "--no-parse-wal"


def test_pg18_verifier_rejected_before_reading_backup(tmp_path):
    p, q, binary, _, _ = _fixture(tmp_path)
    runner, calls = _runner(version="pg_verifybackup (PostgreSQL) 18.7\n")
    with pytest.raises(BackupEvidenceError, match="backup_verifier_major_mismatch"):
        audit(p, q, binary, runner=runner)
    assert len(calls) == 1


def test_wrong_cluster_receipt_is_rejected(tmp_path):
    p, q, binary, _, clone = _fixture(tmp_path)
    clone["databases"][1]["system_identifier"] = "7692004809331994663"
    q.write_text(json.dumps(clone))
    with pytest.raises(BackupEvidenceError, match="schema127_or_dp_clone_receipt_mismatch"):
        audit(p, q, binary, runner=_runner()[0])


def test_schema_drift_is_rejected(tmp_path):
    p, q, binary, _, clone = _fixture(tmp_path)
    clone["databases"][0]["revision"] = "122_company_cost_norms"
    q.write_text(json.dumps(clone))
    with pytest.raises(BackupEvidenceError, match="schema127_or_dp_clone_receipt_mismatch"):
        audit(p, q, binary, runner=_runner()[0])


def test_pg_version_in_base_must_be_17(tmp_path):
    p, q, binary, source, _ = _fixture(tmp_path)
    (Path(source["base_path"]) / "PG_VERSION").write_text("18\n")
    with pytest.raises(BackupEvidenceError, match="unsupported_backup_major_version"):
        audit(p, q, binary, runner=_runner()[0])


def test_physical_verifier_failure_must_not_echo_stderr(tmp_path):
    p, q, binary, _, _ = _fixture(tmp_path)
    with pytest.raises(BackupEvidenceError, match="backup_file_integrity_not_verified") as caught:
        audit(p, q, binary, runner=_runner(verify_rc=1)[0])
    assert "signed-url-in-private-error" not in str(caught.value)


def test_backup_root_symlink_is_rejected(tmp_path):
    p, q, binary, source, _ = _fixture(tmp_path)
    link = tmp_path / "symlink-data"
    link.symlink_to(Path(source["base_path"]), target_is_directory=True)
    source = deepcopy(source)
    source["base_path"] = str(link)
    p.write_text(json.dumps(source))
    with pytest.raises(BackupEvidenceError, match="base_path_not_bound_to_receipt"):
        audit(p, q, binary, runner=_runner()[0])
