from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest
import yaml

from src.modules.domain_regression.registry import (
    ManifestError,
    load_manifest,
    run_registered_cases,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "regressions/procurement/v1/manifest.yaml"


def _manifest_dict() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))


def _write_manifest(tmp_path: Path, data: dict) -> Path:
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    rel = output / f"domain-regression-test-{tmp_path.name}.yaml"
    rel.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return rel


def test_canonical_manifest_validates_and_is_regression_only() -> None:
    manifest = load_manifest(MANIFEST.relative_to(ROOT), root=ROOT)

    assert [case["case_id"] for case in manifest["cases"]] == [
        "DQA-CASE11-CUSTOMER-BOUNDARY",
        "DQA-CASE14-ACTIVE-REVISION",
    ]
    assert all(case["benchmark_class"] == "regression_only" for case in manifest["cases"])
    assert all(case["exposure_status"] == "exposed_regression" for case in manifest["cases"])


def test_duplicate_case_ids_fail_closed(tmp_path: Path) -> None:
    data = _manifest_dict()
    data["cases"].append(copy.deepcopy(data["cases"][0]))
    path = _write_manifest(tmp_path, data)

    with pytest.raises(ManifestError, match="duplicate case_id"):
        load_manifest(path.relative_to(ROOT), root=ROOT)


def test_missing_provenance_fails_schema_validation(tmp_path: Path) -> None:
    data = _manifest_dict()
    del data["cases"][0]["provenance"]["origin_issue"]
    path = _write_manifest(tmp_path, data)

    with pytest.raises(ManifestError, match="schema validation failed"):
        load_manifest(path.relative_to(ROOT), root=ROOT)


def test_frozen_evidence_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    data = _manifest_dict()
    data["cases"][0]["frozen_evidence"]["sha256"] = "0" * 64
    path = _write_manifest(tmp_path, data)

    with pytest.raises(ManifestError, match="sha256 mismatch"):
        load_manifest(path.relative_to(ROOT), root=ROOT)


def test_former_blind_requires_freeze_before_sut_and_post_result_exposure(tmp_path: Path) -> None:
    data = _manifest_dict()
    data["cases"][0]["former_blind"]["truth_frozen_before_sut"] = False
    path = _write_manifest(tmp_path, data)

    with pytest.raises(ManifestError, match="schema validation failed"):
        load_manifest(path.relative_to(ROOT), root=ROOT)


def test_report_is_deterministic_and_sorted() -> None:
    calls: list[list[str]] = []

    def fake_executor(root: Path, nodeids: list[str]) -> int:
        assert root == ROOT
        calls.append(nodeids)
        return 0

    first = run_registered_cases(MANIFEST.relative_to(ROOT), root=ROOT, executor=fake_executor)
    second = run_registered_cases(MANIFEST.relative_to(ROOT), root=ROOT, executor=fake_executor)

    assert first == second
    assert first["schema_version"] == "procurement-regression-report-v1"
    assert first["summary"] == {"total": 2, "passed": 2, "failed": 0}
    assert first["selected_case_ids"] == sorted(first["selected_case_ids"])
    assert first["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert len(calls) == 4


def test_unknown_case_filter_fails_closed() -> None:
    with pytest.raises(ManifestError, match="unknown case_id"):
        run_registered_cases(MANIFEST.relative_to(ROOT), root=ROOT, case_ids={"DOES-NOT-EXIST"}, executor=lambda *_: 0)
