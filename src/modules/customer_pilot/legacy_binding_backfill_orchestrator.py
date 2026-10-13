# ruff: noqa: BLE001, C409  # Preserve original fail-closed control flow and AST.
"""Historical immutable binding backfill orchestration, strictly product-owned.

The immutable-snapshot verifier's original function body, transaction
ownership, row-lock ordering and fail-closed checks remain unchanged.
Legacy module retains the public entrypoint and runtime helper bindings.
"""
from __future__ import annotations

from typing import Any


def run_immutable_backfill(
    *,
    session: Any,
    run: Any,
    case: Any,
    run_result: Any,
    artifact: Any,
    data_root: Any,
    select: Any,
    _result: Any,
    Path: Any,
    _directory: Any,
    EXACT_FILE_SET: Any,
    _regular: Any,
    verify_canonical_bytes: Any,
    json: Any,
    _sha: Any,
    SOURCE_GRAPH_HASH_ALGORITHM: Any,
    VERIFICATION_POLICY_VERSION: Any,
    derive_final_pdf_artifact_identity: Any,
    verify_final_pdf_generation: Any,
    FinalPdfArtifactError: Any,
    ARTIFACT_POLICY_VERSION: Any,
    LegacyBackfillResult: Any,
) -> Any:
    """Backfill only a complete immutable 095 snapshot; never repair it.

    All validation is performed before assigning a mapped value, so errors leave
    both the caller's transaction and the filesystem untouched.
    """
    # PostgreSQL callers lock result first, then artifact.  Re-reading after the
    # lock makes a concurrent caller observe the completed binding instead of
    # racing to write the same nullable columns.
    if hasattr(session, "scalar"):
        from src.modules.customer_pilot.models import PilotArtifact, PilotRunResult

        locked_result = session.scalar(
            select(PilotRunResult)
            .where(PilotRunResult.id == run_result.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        locked_artifact = session.scalar(
            select(PilotArtifact)
            .where(PilotArtifact.id == artifact.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if locked_result is None or locked_artifact is None:
            return _result("CONFLICT", "missing_locked_row")
        run_result, artifact = locked_result, locked_artifact
    if (
        run.customer_id,
        run.project_id,
        case.customer_id,
        case.project_id,
        run_result.customer_id,
        run_result.project_id,
        run_result.procurement_case_id,
        run_result.run_id,
        artifact.customer_id,
        artifact.project_id,
        artifact.procurement_case_id,
        artifact.run_id,
        artifact.run_result_id,
    ) != (
        run.customer_id,
        run.project_id,
        run.customer_id,
        run.project_id,
        run.customer_id,
        run.project_id,
        case.id,
        run.id,
        run.customer_id,
        run.project_id,
        case.id,
        run.id,
        run_result.id,
    ):
        return _result("CONFLICT", "ownership_mismatch")

    new_fields = (
        "requirements_storage_key",
        "requirements_file_sha256",
        "canonical_report_file_sha256",
        "binding_manifest_storage_key",
        "binding_manifest_file_sha256",
        "source_graph_hash_algorithm",
        "report_model_hash",
        "verification_policy_version",
    )
    if all(getattr(run_result, field, None) is not None for field in new_fields):
        from src.modules.customer_pilot.binding_verifier import (
            RunSnapshotBindingError,
            verify_run_snapshot_binding,
        )

        try:
            verify_run_snapshot_binding(run=run, case=case, binding=run_result)
            from src.modules.customer_pilot.artifacts import (
                verify_pilot_artifact_binding,
            )

            verify_pilot_artifact_binding(
                run=run, case=case, result=run_result, artifact=artifact
            )
        except RunSnapshotBindingError:
            return _result("CONFLICT", "invalid_verified_binding")
        except Exception:
            return _result("CONFLICT", "artifact_manifest_invalid")
        return _result("ALREADY_VERIFIED")
    if any(getattr(run_result, field, None) is not None for field in new_fields):
        return _result("CONFLICT", "partial_preexisting_binding")

    root = Path(data_root)
    analysis = (
        root
        / "customer-pilot"
        / run.customer_id
        / run.project_id
        / case.id
        / run.id
        / "analysis"
    )
    try:
        for item in (root, root / "customer-pilot", analysis.parent, analysis):
            _directory(item)
        if {path.name for path in analysis.iterdir()} != set(EXACT_FILE_SET):
            return _result("INCOMPLETE", "exact_snapshot_file_set")
        requirements = _regular(analysis / "requirements.json")
        report = _regular(analysis / "canonical_report.json")
        manifest_bytes = _regular(analysis / "canonical-binding.manifest.json")
        verified = verify_canonical_bytes(
            requirements_bytes=requirements, canonical_report_bytes=report
        )
        manifest = json.loads(manifest_bytes)
    except FileNotFoundError:
        return _result("INCOMPLETE", "missing_snapshot_file")
    except (OSError, ValueError, json.JSONDecodeError):
        return _result("CONFLICT", "invalid_snapshot")

    from src.modules.customer_pilot.legacy_binding_manifest_projection import (
        project_legacy_binding_identities,
    )

    identities, expected_manifest = project_legacy_binding_identities(
        run=run,
        case=case,
        run_result=run_result,
        verified=verified,
        manifest_bytes=manifest_bytes,
        Path=Path,
        _sha=_sha,
        SOURCE_GRAPH_HASH_ALGORITHM=SOURCE_GRAPH_HASH_ALGORITHM,
        VERIFICATION_POLICY_VERSION=VERIFICATION_POLICY_VERSION,
        EXACT_FILE_SET=EXACT_FILE_SET,
    )
    if any(manifest.get(key) != value for key, value in expected_manifest.items()):
        return _result("CONFLICT", "canonical_identity_conflict", identities)
    if run_result.canonical_report_hash != verified.report_model_hash:
        return _result("CONFLICT", "legacy_report_hash_conflict", identities)
    identity = derive_final_pdf_artifact_identity(
        registry_number=run.registry_number,
        run_id=run.id,
        report_model_hash=identities["report_model_hash"],
        customer_id=run.customer_id,
        project_id=run.project_id,
        procurement_case_id=case.id,
    )
    if (
        artifact.artifact_type != "final_pdf"
        or artifact.status != "published"
        or artifact.artifact_key != identity.artifact_key
        or artifact.renderer_version != identity.renderer_version
        or artifact.manifest_relative_path != identity.manifest_relative_path
        or artifact.pdf_relative_path != identity.pdf_relative_path
        or artifact.report_model_hash != identities["report_model_hash"]
        or artifact.source_graph_hash != run_result.source_graph_hash
    ):
        return _result("CONFLICT", "artifact_identity_conflict", identities)
    try:
        generation = verify_final_pdf_generation(
            customer_id=run.customer_id,
            project_id=run.project_id,
            procurement_case_id=case.id,
            run_id=run.id,
            expected={
                "customer_id": run.customer_id,
                "project_id": run.project_id,
                "procurement_case_id": case.id,
                "run_id": run.id,
                "run_result_id": run_result.id,
                "registry_number": run.registry_number,
                "source_analysis_run_id": run_result.source_analysis_run_id,
                "run_namespace_key": run.artifact_key,
                "artifact_key": identity.artifact_key,
                "artifact_type": "final_pdf",
                "renderer_version": identity.renderer_version,
                "requirements_storage_key": identities["requirements_storage_key"],
                "requirements_file_sha256": identities["requirements_file_sha256"],
                "canonical_report_storage_key": run_result.canonical_report_storage_key,
                "canonical_report_file_sha256": identities[
                    "canonical_report_file_sha256"
                ],
                "binding_manifest_storage_key": identities[
                    "binding_manifest_storage_key"
                ],
                "binding_manifest_file_sha256": identities[
                    "binding_manifest_file_sha256"
                ],
                "source_graph_hash": run_result.source_graph_hash,
                "source_graph_hash_algorithm": identities[
                    "source_graph_hash_algorithm"
                ],
                "production_model_hash": run_result.production_model_hash,
                "report_model_hash": identities["report_model_hash"],
                "pdf_relative_path": identity.pdf_relative_path,
                "pdf_sha256": artifact.pdf_sha256,
                "byte_size": artifact.byte_size,
            },
        )
    except FinalPdfArtifactError as exc:
        category = (
            "artifact_pdf_hash_conflict"
            if "PDF" in str(exc)
            else "artifact_manifest_invalid"
        )
        return _result("CONFLICT", category, identities)
    values = {
        **identities,
        "manifest_file_sha256": generation.manifest_file_sha256,
        "artifact_verification_policy_version": ARTIFACT_POLICY_VERSION,
    }
    original = {field: getattr(run_result, field) for field in new_fields}
    artifact_original = (
        artifact.manifest_file_sha256,
        artifact.verification_policy_version,
    )
    for field in new_fields:
        setattr(run_result, field, values[field])
    artifact.manifest_file_sha256 = values["manifest_file_sha256"]
    artifact.verification_policy_version = values[
        "artifact_verification_policy_version"
    ]
    try:
        session.flush()
        from src.modules.customer_pilot.artifacts import verify_pilot_artifact_binding
        from src.modules.customer_pilot.binding_verifier import (
            verify_run_snapshot_binding,
        )

        verify_run_snapshot_binding(run=run, case=case, binding=run_result)
        verify_pilot_artifact_binding(
            run=run, case=case, result=run_result, artifact=artifact
        )
    except Exception:
        for field, value in original.items():
            setattr(run_result, field, value)
        artifact.manifest_file_sha256, artifact.verification_policy_version = (
            artifact_original
        )
        return _result("CONFLICT", "artifact_manifest_invalid", identities)
    return LegacyBackfillResult(
        "BACKFILLED",
        tuple((*new_fields, "manifest_file_sha256", "verification_policy_version")),
        values,
        None,
        True,
    )
