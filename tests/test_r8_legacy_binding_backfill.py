from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts.acceptance.run_r8_migration_backfill import _fixture as production_fixture
from src.modules.customer_pilot.legacy_binding_backfill import (
    backfill_legacy_run_binding,
)


class Session:
    def __init__(self):
        self.flushes = 0

    def flush(self):
        self.flushes += 1


class Result(SimpleNamespace):
    @property
    def is_verified_snapshot_binding(self):
        return all(
            getattr(self, field, None)
            for field in (
                "requirements_storage_key",
                "requirements_file_sha256",
                "canonical_report_file_sha256",
                "binding_manifest_storage_key",
                "binding_manifest_file_sha256",
                "source_graph_hash_algorithm",
                "report_model_hash",
                "verification_policy_version",
            )
        )


def _fixture(tmp_path: Path, monkeypatch, missing=False, conflict=False):
    ids = production_fixture(tmp_path, "RECOVERABLE", 1)
    run = SimpleNamespace(
        customer_id=ids["customer_id"],
        project_id=ids["project_id"],
        id=ids["run_id"],
        registry_number="0379100000726000101",
        artifact_key=ids["run_namespace_key"],
    )
    case = SimpleNamespace(
        customer_id=ids["customer_id"], project_id=ids["project_id"], id=ids["case_id"]
    )
    result = Result(
        id=ids["run_result_id"],
        customer_id=ids["customer_id"],
        project_id=ids["project_id"],
        procurement_case_id=ids["case_id"],
        run_id=ids["run_id"],
        source_analysis_run_id=ids["source_run_id"],
        canonical_report_storage_key=ids["canonical_report_storage_key"],
        canonical_report_hash="f" * 64 if conflict else ids["legacy_hash"],
        source_graph_hash=ids["source_graph_hash"],
        production_model_hash=ids["production_model_hash"],
        requirements_storage_key=None,
        requirements_file_sha256=None,
        canonical_report_file_sha256=None,
        binding_manifest_storage_key=None,
        binding_manifest_file_sha256=None,
        source_graph_hash_algorithm=None,
        report_model_hash=None,
        verification_policy_version=None,
    )
    artifact = SimpleNamespace(
        id=ids["artifact_id"],
        customer_id=ids["customer_id"],
        project_id=ids["project_id"],
        procurement_case_id=ids["case_id"],
        run_id=ids["run_id"],
        run_result_id=ids["run_result_id"],
        artifact_type="final_pdf",
        artifact_key=ids["artifact_key"],
        report_model_hash=ids["legacy_hash"],
        source_graph_hash=ids["source_graph_hash"],
        renderer_version=ids["renderer_version"],
        manifest_relative_path=ids["manifest_relative_path"],
        pdf_relative_path=ids["pdf_relative_path"],
        pdf_sha256=ids["pdf_sha256"],
        byte_size=ids["byte_size"],
        status="published",
        manifest_file_sha256=None,
        verification_policy_version=None,
    )
    if missing:
        (tmp_path / ids["canonical_report_storage_key"]).with_name(
            "canonical-binding.manifest.json"
        ).unlink()
    return Session(), run, case, result, artifact


def test_valid_legacy_bundle_backfills_then_is_idempotent(tmp_path, monkeypatch):
    session, run, case, result, artifact = _fixture(tmp_path, monkeypatch)
    assert (
        backfill_legacy_run_binding(
            session=session,
            run=run,
            case=case,
            run_result=result,
            artifact=artifact,
            data_root=tmp_path,
        ).status
        == "BACKFILLED"
    )
    assert (
        result.report_model_hash
        and artifact.manifest_file_sha256
        and artifact.verification_policy_version
    )
    assert (
        backfill_legacy_run_binding(
            session=session,
            run=run,
            case=case,
            run_result=result,
            artifact=artifact,
            data_root=tmp_path,
        ).status
        == "ALREADY_VERIFIED"
    )


def test_missing_manifest_is_fail_closed_without_writes(tmp_path, monkeypatch):
    session, run, case, result, artifact = _fixture(tmp_path, monkeypatch, missing=True)
    assert (
        backfill_legacy_run_binding(
            session=session,
            run=run,
            case=case,
            run_result=result,
            artifact=artifact,
            data_root=tmp_path,
        ).status
        == "INCOMPLETE"
    )
    assert (
        result.report_model_hash is None
        and artifact.manifest_file_sha256 is None
        and session.flushes == 0
    )


def test_conflicting_legacy_hash_is_fail_closed_without_writes(tmp_path, monkeypatch):
    session, run, case, result, artifact = _fixture(
        tmp_path, monkeypatch, conflict=True
    )
    assert (
        backfill_legacy_run_binding(
            session=session,
            run=run,
            case=case,
            run_result=result,
            artifact=artifact,
            data_root=tmp_path,
        ).status
        == "CONFLICT"
    )
    assert (
        result.report_model_hash is None
        and artifact.manifest_file_sha256 is None
        and session.flushes == 0
    )

def test_mismatched_tenant_ownership_rejects_before_any_mutation(tmp_path, monkeypatch):
    session, run, case, result, artifact = _fixture(tmp_path, monkeypatch)
    run.customer_id = "other-customer"
    before = (result.report_model_hash, artifact.manifest_file_sha256)
    outcome = backfill_legacy_run_binding(
        session=session, run=run, case=case, run_result=result,
        artifact=artifact, data_root=tmp_path,
    )
    assert outcome.status == "CONFLICT"
    assert outcome.error_category == "ownership_mismatch"
    assert outcome.mutation_performed is False
    assert (result.report_model_hash, artifact.manifest_file_sha256) == before
    assert session.flushes == 0


def test_partial_preexisting_snapshot_binding_rejects_without_repair(tmp_path, monkeypatch):
    session, run, case, result, artifact = _fixture(tmp_path, monkeypatch)
    result.requirements_storage_key = "tampered/requirements.json"
    outcome = backfill_legacy_run_binding(
        session=session, run=run, case=case, run_result=result,
        artifact=artifact, data_root=tmp_path,
    )
    assert outcome.status == "CONFLICT"
    assert outcome.error_category == "partial_preexisting_binding"
    assert outcome.mutation_performed is False
    assert result.requirements_storage_key == "tampered/requirements.json"
    assert result.report_model_hash is None
    assert session.flushes == 0


def test_unexpected_snapshot_file_rejects_before_writing_binding(tmp_path, monkeypatch):
    session, run, case, result, artifact = _fixture(tmp_path, monkeypatch)
    source_dir = (tmp_path / result.canonical_report_storage_key).parent
    (source_dir / "unlisted.txt").write_text("must not be accepted")
    outcome = backfill_legacy_run_binding(
        session=session, run=run, case=case, run_result=result,
        artifact=artifact, data_root=tmp_path,
    )
    assert outcome.status == "INCOMPLETE"
    assert outcome.error_category == "exact_snapshot_file_set"
    assert outcome.mutation_performed is False
    assert result.report_model_hash is None
    assert session.flushes == 0


def test_symlink_inside_snapshot_rejected_without_path_traversal(tmp_path, monkeypatch):
    session, run, case, result, artifact = _fixture(tmp_path, monkeypatch)
    source_dir = (tmp_path / result.canonical_report_storage_key).parent
    requirements = source_dir / "requirements.json"
    external = tmp_path / "external-requirements.json"
    requirements.rename(external)
    requirements.symlink_to(external)
    outcome = backfill_legacy_run_binding(
        session=session, run=run, case=case, run_result=result,
        artifact=artifact, data_root=tmp_path,
    )
    assert outcome.status == "CONFLICT"
    assert outcome.error_category == "invalid_snapshot"
    assert outcome.mutation_performed is False
    assert external.is_file() and requirements.is_symlink()
    assert result.report_model_hash is None
    assert artifact.manifest_file_sha256 is None
    assert session.flushes == 0


def test_orm_values_restored_when_flush_fails(tmp_path, monkeypatch):
    session, run, case, result, artifact = _fixture(tmp_path, monkeypatch)
    def fail_flush():
        session.flushes += 1
        raise RuntimeError("simulated local flush failure")
    monkeypatch.setattr(session, "flush", fail_flush)
    outcome = backfill_legacy_run_binding(
        session=session, run=run, case=case, run_result=result,
        artifact=artifact, data_root=tmp_path,
    )
    assert outcome.status == "CONFLICT"
    assert outcome.error_category == "artifact_manifest_invalid"
    assert outcome.mutation_performed is False
    assert all(getattr(result, field) is None for field in (
        "requirements_storage_key", "requirements_file_sha256",
        "canonical_report_file_sha256", "binding_manifest_storage_key",
        "binding_manifest_file_sha256", "source_graph_hash_algorithm",
        "report_model_hash", "verification_policy_version",
    ))
    assert artifact.manifest_file_sha256 is None
    assert artifact.verification_policy_version is None
    assert session.flushes == 1
    # This checks in-memory restoration; caller still owns DB rollback.


def test_backfill_facade_resolves_runtime_directory_guard(monkeypatch, tmp_path):
    session, run, case, result, artifact = _fixture(tmp_path, monkeypatch)
    from src.modules.customer_pilot import legacy_binding_backfill as legacy
    verified = []
    def forbid_directory(path):
        verified.append(path)
        raise ValueError("unsafe_filesystem")
    monkeypatch.setattr(legacy, "_directory", forbid_directory)
    outcome = legacy.backfill_legacy_run_binding(
        session=session, run=run, case=case, run_result=result,
        artifact=artifact, data_root=tmp_path,
    )
    assert outcome.status == "CONFLICT"
    assert outcome.error_category == "invalid_snapshot"
    assert outcome.mutation_performed is False
    assert len(verified) == 1
    assert result.report_model_hash is None
    assert artifact.manifest_file_sha256 is None
    assert session.flushes == 0
