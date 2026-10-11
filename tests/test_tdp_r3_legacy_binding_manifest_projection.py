"""Original immutable binding identity/manifest projection is source-preserving."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace

from src.modules.customer_pilot.legacy_binding_manifest_projection import (
    project_legacy_binding_identities,
)

ORIGINAL_THREE_ASSIGNMENTS_SHA256 = "563caa2528d86cd307850dfac24128a4d4f616791faff5e1d8a3b65e309cb24c"
SOURCE = (
    Path(__file__).resolve().parents[1]
    / "src/modules/customer_pilot/legacy_binding_manifest_projection.py"
)


def test_original_three_assignments_have_identical_ast():
    fn = next(
        n for n in ast.parse(SOURCE.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "project_legacy_binding_identities"
    )
    names = ("expected_base", "identities", "expected_manifest")
    original_assignments = [
        n for n in fn.body
        if isinstance(n, ast.Assign)
        and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id in names
    ]
    assert [n.targets[0].id for n in original_assignments] == list(names)
    sha = hashlib.sha256(
        ast.dump(ast.Module(body=original_assignments, type_ignores=[]), include_attributes=False).encode()
    ).hexdigest()
    assert sha == ORIGINAL_THREE_ASSIGNMENTS_SHA256


def test_projection_retains_tenant_scoped_paths_and_exact_source_hashes():
    run = SimpleNamespace(customer_id="tenant1", project_id="project2",
                          id="run3", registry_number="0372200172326000015", artifact_key="x")
    case = SimpleNamespace(id="case4")
    result = SimpleNamespace(
        source_analysis_run_id="source5", source_graph_hash="g" * 64,
        production_model_hash="p" * 64,
        canonical_report_storage_key="customer-pilot/canonical/report.json",
    )
    verified = SimpleNamespace(
        requirements_file_sha256="a" * 64,
        canonical_report_file_sha256="b" * 64,
        report_model_hash="c" * 64,
    )
    expected, manifest = project_legacy_binding_identities(
        run=run,case=case,run_result=result,verified=verified,
        manifest_bytes=b"source-locked",
        Path=Path,_sha=lambda b: hashlib.sha256(b).hexdigest(),
        SOURCE_GRAPH_HASH_ALGORITHM="sha256-v1",
        VERIFICATION_POLICY_VERSION="verification-v1",
        EXACT_FILE_SET=("requirements.json","canonical_report.json","canonical-binding.manifest.json"),
    )
    assert expected["requirements_storage_key"] == "customer-pilot/tenant1/project2/case4/run3/analysis/requirements.json"
    assert expected["canonical_report_file_sha256"] == "b" * 64
    assert expected["binding_manifest_file_sha256"] == hashlib.sha256(b"source-locked").hexdigest()
    assert manifest["procurement_case_id"] == "case4"
    assert manifest["run_id"] == "run3"
    assert manifest["registry_number"] == "0372200172326000015"
    assert manifest["source_graph_hash"] == "g" * 64
    assert manifest["source_graph_hash_algorithm"] == "sha256-v1"
    assert manifest["requirements_relative_path"] == expected["requirements_storage_key"]
    assert manifest["exact_file_set"] == ("requirements.json","canonical_report.json","canonical-binding.manifest.json")
    assert result.source_graph_hash == "g" * 64
