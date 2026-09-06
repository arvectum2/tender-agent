from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

import pytest

import scripts.run_benchmark_control_rerun as control
from scripts.run_macmini_autonomous_procurement import E2EBlocked
from src.modules.benchmark_pipeline.calibration import (
    bind_discovery_context,
    build_discovery_context,
)
from src.modules.benchmark_pipeline.contract import (
    source_bundle_sha256,
    write_artifact,
)
from src.modules.benchmark_pipeline.workflow import (
    freeze_blind_labels,
    prepare_evaluator_bundle,
)

ACQUIRED = "2026-09-06T05:00:00+00:00"
PREPARED = "2026-09-06T05:01:00+00:00"
EVALUATED = "2026-09-06T05:02:00+00:00"
FROZEN = "2026-09-06T05:03:00+00:00"


def _build_frozen_case(case_dir: Path) -> dict:
    source_dir = case_dir / "source"
    source_dir.mkdir(parents=True)
    source = source_dir / "notice.txt"
    source.write_text("source-only procurement evidence", encoding="utf-8")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    documents = [
        {
            "path": "source/notice.txt",
            "sha256": source_hash,
            "source_url": "https://example.test/notice/TEST-001/notice.txt",
        }
    ]
    manifest = {
        "schema_version": "1.1.0",
        "case_id": "control-case-001",
        "procurement": {
            "notice_number": "TEST-001",
            "title": "Source-only procurement",
            "customer_name": "Test Customer",
            "source": "public_eis_html_44fz",
            "law": "44-ФЗ",
            "source_url": "https://example.test/notice/TEST-001",
        },
        "source_urls": [
            "https://example.test/notice/TEST-001",
            "https://example.test/notice/TEST-001/notice.txt",
        ],
        "acquired_at": ACQUIRED,
        "documents": documents,
        "source_scope": "real-source-shaped frozen control fixture",
        "source_bundle_sha256": source_bundle_sha256(documents),
        "source_conflict": False,
        "provenance_sufficient": True,
    }
    context = build_discovery_context(
        supplier_profile={
            "supplier_id": "fixture-electrical",
            "criteria": {"categories": ["electrical equipment"]},
        },
        registry_number="TEST-001",
        source="public_eis_html_44fz",
        law="44-ФЗ",
        as_of=ACQUIRED,
        query="TEST-001",
    )
    manifest = bind_discovery_context(manifest, context)
    bundle = prepare_evaluator_bundle(manifest, prepared_at=PREPARED)
    discovery = {
        "schema_version": "1.1.0",
        "case_id": manifest["case_id"],
        "source_bundle_sha256": manifest["source_bundle_sha256"],
        "label": "IRRELEVANT",
        "reason": "Frozen fixture judgment.",
        "confidence": 0.99,
        "evidence": [{"source_ref": "source/notice.txt", "locator": "document"}],
        "evaluator": "independent-evaluator",
        "evaluated_at": EVALUATED,
    }
    truth = {
        "schema_version": "1.1.0",
        "case_id": manifest["case_id"],
        "source_bundle_sha256": manifest["source_bundle_sha256"],
        "facts": [
            {
                "field": "procurement_subject",
                "value": "Source-only procurement",
                "materiality": "MATERIAL",
                "evidence": [{"source_ref": "source/notice.txt", "locator": "document"}],
            }
        ],
        "confidence": 0.99,
        "evaluator": "independent-evaluator",
        "evaluated_at": EVALUATED,
    }
    freeze = freeze_blind_labels(bundle, discovery, truth, frozen_at=FROZEN)

    write_artifact(case_dir / "case_manifest.json", manifest, "case_manifest")
    write_artifact(case_dir / "evaluator_bundle.json", bundle, "evaluator_bundle")
    write_artifact(
        case_dir / "blind_discovery_label.json", discovery, "blind_discovery_label"
    )
    write_artifact(case_dir / "blind_document_truth.json", truth, "blind_document_truth")
    write_artifact(case_dir / "frozen_label.json", freeze, "frozen_label")
    return manifest


def test_copy_frozen_case_preserves_only_immutable_inputs(tmp_path: Path) -> None:
    source_case = tmp_path / "baseline"
    _build_frozen_case(source_case)
    (source_case / "sut_runtime_response.json").write_text("{}\n", encoding="utf-8")
    (source_case / "comparison_result.json").write_text("{}\n", encoding="utf-8")
    target = tmp_path / "control"

    copied = control.copy_frozen_case(source_case, target)

    assert copied["case_id"] == "control-case-001"
    assert (target / "source" / "notice.txt").read_bytes() == (
        source_case / "source" / "notice.txt"
    ).read_bytes()
    for name, _kind in control.IMMUTABLE_ARTIFACTS:
        assert (target / name).read_bytes() == (source_case / name).read_bytes()
    assert not (target / "sut_runtime_response.json").exists()
    assert not (target / "comparison_result.json").exists()


def test_exact_source_hash_comparison_is_multiset_sensitive(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    manifest = _build_frozen_case(case_dir)
    expected = control.expected_source_hashes(manifest)

    control.assert_exact_source_hashes(manifest=manifest, observed=expected.copy())

    wrong = Counter({"f" * 64: 1})
    with pytest.raises(E2EBlocked) as exc_info:
        control.assert_exact_source_hashes(manifest=manifest, observed=wrong)
    assert exc_info.value.code == "control_source_bundle_mismatch"

    duplicated = expected.copy()
    duplicated.update(expected)
    with pytest.raises(E2EBlocked) as exc_info:
        control.assert_exact_source_hashes(manifest=manifest, observed=duplicated)
    assert exc_info.value.code == "control_source_bundle_mismatch"


def test_control_rerun_refuses_to_analyze_when_fresh_source_bytes_differ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_case = tmp_path / "baseline"
    _build_frozen_case(source_case)
    target = tmp_path / "control"

    class FakeClient:
        analyzed = False

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def search(self, **_kwargs):
            return {
                "cards": [
                    {
                        "reestr_number": "TEST-001",
                        "source": "public_eis_html_44fz",
                        "source_url": "https://example.test/notice/TEST-001",
                    }
                ]
            }

        def get_run(self, run_id: str):
            return {
                "run_id": run_id,
                "analysis_mode": "not_started",
                "final_recommendation": None,
                "events": [],
                "files": [],
                "status": "draft",
            }

        def analyze(self, _run_id: str):
            type(self).analyzed = True
            raise AssertionError("analysis must not start on source mismatch")

    monkeypatch.setattr(control, "BackendClient", FakeClient)
    monkeypatch.setattr(control, "source_only_handoff", lambda *_args, **_kwargs: {"run_id": "run-1"})
    monkeypatch.setattr(
        control,
        "runtime_source_hashes",
        lambda **_kwargs: Counter({"f" * 64: 1}),
    )

    with pytest.raises(E2EBlocked) as exc_info:
        control.run_control(
            source_case_dir=source_case,
            output_dir=target,
            backend_url="http://127.0.0.1:8000",
            runtime_version="fixed-main",
            query=None,
            search_days=120,
            timeout_seconds=30,
        )

    assert exc_info.value.code == "control_source_bundle_mismatch"
    assert FakeClient.analyzed is False
    assert not (target / "sut_runtime_response.json").exists()


def test_control_rerun_analyzes_only_after_exact_source_match_and_saves_raw_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_case = tmp_path / "baseline"
    manifest = _build_frozen_case(source_case)
    target = tmp_path / "control"

    class FakeClient:
        analyzed = False

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def search(self, **_kwargs):
            return {
                "cards": [
                    {
                        "reestr_number": "TEST-001",
                        "source": "public_eis_html_44fz",
                        "source_url": "https://example.test/notice/TEST-001",
                    }
                ]
            }

        def get_run(self, run_id: str):
            if not type(self).analyzed:
                return {
                    "run_id": run_id,
                    "analysis_mode": "not_started",
                    "final_recommendation": None,
                    "events": [],
                    "files": [],
                    "status": "draft",
                }
            return {
                "run_id": run_id,
                "status": "completed",
                "analysis_mode": "llm_tender_operator_provider",
                "tender_title": "Source-only procurement",
                "customer_name": "Test Customer",
                "final_recommendation": {},
                "events": [
                    {
                        "event_type": "analysis_completed",
                        "timestamp": "2026-09-06T05:04:00Z",
                    }
                ],
            }

        def analyze(self, _run_id: str):
            type(self).analyzed = True
            return {"status": "completed"}

    monkeypatch.setattr(control, "BackendClient", FakeClient)
    monkeypatch.setattr(control, "source_only_handoff", lambda *_args, **_kwargs: {"run_id": "run-2"})
    monkeypatch.setattr(
        control,
        "runtime_source_hashes",
        lambda **_kwargs: control.expected_source_hashes(manifest),
    )

    result = control.run_control(
        source_case_dir=source_case,
        output_dir=target,
        backend_url="http://127.0.0.1:8000",
        runtime_version="fixed-main",
        query=None,
        search_days=120,
        timeout_seconds=30,
    )

    assert FakeClient.analyzed is True
    assert result["status"] == "BENCHMARK_CONTROL_RUNTIME_READY"
    assert result["run_id"] == "run-2"
    assert result["runtime_version"] == "fixed-main"
    assert (target / "sut_runtime_response.json").exists()
    assert '"analysis_mode": "llm_tender_operator_provider"' in (
        target / "sut_runtime_response.json"
    ).read_text(encoding="utf-8")
    assert (target / "control-rerun-result.json").exists()
