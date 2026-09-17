from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

MANIFEST_SCHEMA_VERSION = "procurement-regression-manifest-v1"
REPORT_SCHEMA_VERSION = "procurement-regression-report-v1"
DEFAULT_MANIFEST = Path("regressions/procurement/v1/manifest.yaml")
DEFAULT_SCHEMA = Path("schemas/procurement_regression_manifest_v1.schema.json")


class ManifestError(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_repo_path(root: Path, raw: str) -> Path:
    candidate = (root / raw).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ManifestError(f"path escapes repository root: {raw}")
    return candidate


def _validate_schema(manifest: dict[str, Any], schema: dict[str, Any]) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda err: list(err.path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "<root>"
        raise ManifestError(f"schema validation failed at {location}: {first.message}")


def _validate_semantics(manifest: dict[str, Any], root: Path) -> None:
    seen: set[str] = set()
    for case in manifest["cases"]:
        case_id = case["case_id"]
        if case_id in seen:
            raise ManifestError(f"duplicate case_id: {case_id}")
        seen.add(case_id)

        evidence = case["frozen_evidence"]
        evidence_path = _safe_repo_path(root, evidence["path"])
        if not evidence_path.is_file():
            raise ManifestError(f"{case_id}: frozen evidence missing: {evidence['path']}")
        actual = _sha256(evidence_path)
        if actual != evidence["sha256"]:
            raise ManifestError(
                f"{case_id}: frozen evidence sha256 mismatch: expected {evidence['sha256']}, got {actual}"
            )

        for ref in case["provenance"]["evidence_refs"]:
            if ref.startswith(("http://", "https://", "github:")):
                continue
            ref_path = _safe_repo_path(root, ref)
            if not ref_path.exists():
                raise ManifestError(f"{case_id}: provenance reference missing: {ref}")

        for nodeid in case["runner"]["pytest_nodeids"]:
            test_path = nodeid.split("::", 1)[0]
            if not test_path.startswith("tests/"):
                raise ManifestError(f"{case_id}: runner must target repository tests only: {nodeid}")
            if not _safe_repo_path(root, test_path).is_file():
                raise ManifestError(f"{case_id}: pytest target missing: {nodeid}")

        former_blind = case.get("former_blind")
        if former_blind:
            freeze_ref = former_blind["freeze_ref"]
            if freeze_ref.startswith(("http://", "https://", "github:")):
                continue
            if not _safe_repo_path(root, freeze_ref).exists():
                raise ManifestError(f"{case_id}: former-blind freeze reference missing: {freeze_ref}")


def load_manifest(
    manifest_path: Path | str = DEFAULT_MANIFEST,
    *,
    root: Path | str | None = None,
    schema_path: Path | str = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    repo_root = Path(root or Path.cwd()).resolve()
    manifest_file = _safe_repo_path(repo_root, str(manifest_path))
    schema_file = _safe_repo_path(repo_root, str(schema_path))
    manifest = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ManifestError("manifest root must be an object")
    _validate_schema(manifest, schema)
    _validate_semantics(manifest, repo_root)
    return manifest


def _default_pytest_executor(root: Path, nodeids: list[str]) -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *nodeids],
        cwd=root,
        check=False,
        text=True,
    )
    return int(completed.returncode)


def run_registered_cases(
    manifest_path: Path | str = DEFAULT_MANIFEST,
    *,
    root: Path | str | None = None,
    case_ids: set[str] | None = None,
    components: set[str] | None = None,
    executor: Callable[[Path, list[str]], int] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root or Path.cwd()).resolve()
    manifest_file = _safe_repo_path(repo_root, str(manifest_path))
    manifest = load_manifest(manifest_path, root=repo_root)
    available_ids = {case["case_id"] for case in manifest["cases"]}
    unknown = sorted((case_ids or set()) - available_ids)
    if unknown:
        raise ManifestError("unknown case_id(s): " + ", ".join(unknown))

    selected = [
        case
        for case in manifest["cases"]
        if (not case_ids or case["case_id"] in case_ids)
        and (not components or case["component"] in components)
    ]
    selected.sort(key=lambda case: case["case_id"])
    if not selected:
        raise ManifestError("no regression cases selected")

    run_pytest = executor or _default_pytest_executor
    results: list[dict[str, Any]] = []
    for case in selected:
        nodeids = list(case["runner"]["pytest_nodeids"])
        returncode = run_pytest(repo_root, nodeids)
        results.append(
            {
                "case_id": case["case_id"],
                "component": case["component"],
                "regime": case["regime"],
                "status": "passed" if returncode == 0 else "failed",
                "pytest_nodeids": nodeids,
            }
        )

    passed = sum(row["status"] == "passed" for row in results)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "manifest_schema_version": manifest["schema_version"],
        "manifest_sha256": _sha256(manifest_file),
        "selected_case_ids": [row["case_id"] for row in results],
        "results": results,
        "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed},
    }
