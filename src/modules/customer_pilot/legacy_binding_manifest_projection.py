"""Pure deterministic source-identity projection for immutable legacy bindings.

All three source assignment bodies are moved without logic or AST changes;
no filesystem access, persistence, LLM inference or mutable defaults.
"""
from __future__ import annotations

from typing import Any


def project_legacy_binding_identities(
    *,
    run: Any,
    case: Any,
    run_result: Any,
    verified: Any,
    manifest_bytes: bytes,
    Path: Any,
    _sha: Any,
    SOURCE_GRAPH_HASH_ALGORITHM: str,
    VERIFICATION_POLICY_VERSION: str,
    EXACT_FILE_SET: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_base = str(
        Path("customer-pilot")
        / run.customer_id
        / run.project_id
        / case.id
        / run.id
        / "analysis"
    )
    identities = {
        "requirements_storage_key": f"{expected_base}/requirements.json",
        "requirements_file_sha256": verified.requirements_file_sha256,
        "canonical_report_file_sha256": verified.canonical_report_file_sha256,
        "binding_manifest_storage_key": f"{expected_base}/canonical-binding.manifest.json",
        "binding_manifest_file_sha256": _sha(manifest_bytes),
        "source_graph_hash_algorithm": SOURCE_GRAPH_HASH_ALGORITHM,
        "report_model_hash": verified.report_model_hash,
        "verification_policy_version": VERIFICATION_POLICY_VERSION,
    }
    expected_manifest = {
        "customer_id": run.customer_id,
        "project_id": run.project_id,
        "procurement_case_id": case.id,
        "run_id": run.id,
        "registry_number": run.registry_number,
        "source_analysis_run_id": run_result.source_analysis_run_id,
        "source_graph_hash": run_result.source_graph_hash,
        "source_graph_hash_algorithm": SOURCE_GRAPH_HASH_ALGORITHM,
        "production_model_hash": run_result.production_model_hash,
        "report_model_hash": verified.report_model_hash,
        "requirements_relative_path": identities["requirements_storage_key"],
        "requirements_file_sha256": identities["requirements_file_sha256"],
        "canonical_report_relative_path": run_result.canonical_report_storage_key,
        "canonical_report_file_sha256": identities["canonical_report_file_sha256"],
        "exact_file_set": EXACT_FILE_SET,
        "verification_policy_version": VERIFICATION_POLICY_VERSION,
    }
    return identities, expected_manifest
