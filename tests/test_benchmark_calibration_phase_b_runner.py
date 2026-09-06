from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

import scripts.run_benchmark_calibration_phase_b as runner
from src.modules.benchmark_pipeline import (
    BenchmarkContractError,
    bind_discovery_context,
    build_discovery_context,
    prepare_evaluator_bundle,
    source_bundle_sha256,
    write_artifact,
)


PREPARED = "2026-09-06T08:00:00+00:00"
EVALUATED = "2026-09-06T08:01:00+00:00"
FROZEN = "2026-09-06T08:02:00+00:00"
ANALYSIS_COMPLETED = "2026-09-06T08:03:00+00:00"


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _case(tmp_path: Path) -> tuple[Path, Path]:
    case_dir = tmp_path / "calibration-rerun"
    source_dir = case_dir / "source"
    source_dir.mkdir(parents=True)
    source_path = source_dir / "notice.txt"
    source_path.write_text("public calibration fixture", encoding="utf-8")
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    documents = [
        {
            "path": "source/notice.txt",
            "sha256": source_sha,
            "source_url": "https://example.test/notice/TEST-001",
        }
    ]
    manifest = {
        "schema_version": "1.1.0",
        "case_id": "calibration-rerun-1",
        "procurement": {
            "notice_number": "TEST-001",
            "title": "Calibration procurement",
            "customer_name": "Fixture Customer",
            "law": "44-ФЗ",
            "source": "public_eis_html_44fz",
            "source_url": "https://example.test/notice/TEST-001",
        },
        "source_urls": ["https://example.test/notice/TEST-001"],
        "acquired_at": "2026-09-06T07:59:00+00:00",
        "documents": documents,
        "source_scope": "sanitized public calibration fixture",
        "source_bundle_sha256": source_bundle_sha256(documents),
        "source_conflict": False,
        "provenance_sufficient": True,
    }
    context = build_discovery_context(
        supplier_profile={
            "supplier_id": "fixture-electrical",
            "criteria": {"keywords": ["cable"], "regions": ["Moscow region"]},
        },
        registry_number="TEST-001",
        source="public_eis_html_44fz",
        law="44-ФЗ",
        as_of=manifest["acquired_at"],
        query="cable",
    )
    manifest = bind_discovery_context(manifest, context)
    write_artifact(case_dir / "case_manifest.json", manifest, "case_manifest")
    evaluator = prepare_evaluator_bundle(manifest, prepared_at=PREPARED)
    write_artifact(case_dir / "evaluator_bundle.json", evaluator, "evaluator_bundle")
    _write_json(
        case_dir / "phase-a-result.json",
        {
            "status": "BENCHMARK_CALIBRATION_PHASE_A_READY",
            "case_id": manifest["case_id"],
            "run_id": "toa-run-fixture",
        },
    )

    discovery = {
        "schema_version": "1.1.0",
        "case_id": manifest["case_id"],
        "source_bundle_sha256": manifest["source_bundle_sha256"],
        "label": "IRRELEVANT",
        "reason": "Source candidate is outside the frozen supplier profile.",
        "confidence": 0.99,
        "evidence": [{"source_ref": "source/notice.txt", "locator": "fixture"}],
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
                "value": "Calibration procurement",
                "evidence": [{"source_ref": "source/notice.txt", "locator": "fixture"}],
                "confidence": 0.99,
                "abstention": "ASSERTED",
                "materiality": "MATERIAL",
            }
        ],
        "confidence": 0.99,
        "evaluator": "independent-evaluator",
        "evaluated_at": EVALUATED,
    }
    labels_zip = tmp_path / "labels.zip"
    with zipfile.ZipFile(labels_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("blind_discovery_label.json", json.dumps(discovery, ensure_ascii=False))
        archive.writestr("blind_document_truth.json", json.dumps(truth, ensure_ascii=False))
    return case_dir, labels_zip


class _FakeClient:
    analyzed = False
    analysis_preexists = False

    def __init__(self, *args, **kwargs):
        del args, kwargs

    def get_run(self, run_id: str) -> dict:
        assert run_id == "toa-run-fixture"
        if not self.analyzed and not self.analysis_preexists:
            return {
                "run_id": run_id,
                "analysis_mode": "not_started",
                "final_recommendation": None,
                "events": [],
            }
        return {
            "run_id": run_id,
            "analysis_mode": "llm_tender_operator_provider",
            "tender_title": "Calibration procurement",
            "customer_name": "Fixture Customer",
            "final_recommendation": {
                "economics": [],
                "key_requirements": [],
                "risks": [],
                "rationale": [],
                "open_questions": [],
                "manual_checks": [],
                "label": "manual review",
                "recommendation": "manual_review_required",
                "trace": "fixture trace",
            },
            "events": [
                {"event_type": "analysis_started", "timestamp": "2026-09-06T08:02:30+00:00"},
                {"event_type": "analysis_completed", "timestamp": ANALYSIS_COMPLETED},
            ],
        }

    def analyze(self, run_id: str) -> dict:
        assert run_id == "toa-run-fixture"
        type(self).analyzed = True
        return {"run_id": run_id}


def _install_fake_backend(
    monkeypatch: pytest.MonkeyPatch,
    *,
    analysis_preexists: bool = False,
) -> None:
    _FakeClient.analyzed = False
    _FakeClient.analysis_preexists = analysis_preexists
    monkeypatch.setattr(runner, "BackendClient", _FakeClient)
    monkeypatch.setattr(runner, "_auth_credentials_from_env", lambda: None)
    monkeypatch.setattr(runner, "_now_iso", lambda: FROZEN)


def test_phase_b_runner_freezes_before_analysis_and_packages_audited_result(tmp_path, monkeypatch):
    case_dir, labels_zip = _case(tmp_path)
    _install_fake_backend(monkeypatch)
    labels_sha = hashlib.sha256(labels_zip.read_bytes()).hexdigest()

    result = runner.run_phase_b(
        case_dir=case_dir,
        backend_url="http://127.0.0.1:8000",
        runtime_version="fixture-runtime@1",
        labels_zip=labels_zip,
        expected_labels_zip_sha256=labels_sha,
        timeout_seconds=5,
    )

    assert result["status"] == "BENCHMARK_CALIBRATION_PHASE_B_COMPLETE"
    assert result["freeze_created_this_run"] is True
    assert result["labels_zip_sha256"] == labels_sha
    assert result["runtime_produced_at"] == ANALYSIS_COMPLETED
    assert result["discovery"]["outcome"] == "NOT_SCORABLE"
    assert result["document"]["tp"] == 1
    assert result["document"]["fn"] == 0
    assert (case_dir / "frozen_label.json").exists()
    assert (case_dir / "sut_runtime_response.json").exists()
    assert (case_dir / "normalization_audit.json").exists()
    assert (case_dir / "comparison_result.json").exists()
    assert (case_dir / "review_state.json").exists()
    archive = Path(result["artifact_zip"])
    assert archive.is_file()
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == result["artifact_zip_sha256"]


def test_phase_b_runner_refuses_retroactive_freeze_after_analysis(tmp_path, monkeypatch):
    case_dir, labels_zip = _case(tmp_path)
    _install_fake_backend(monkeypatch, analysis_preexists=True)

    with pytest.raises(Exception, match="analysis"):
        runner.run_phase_b(
            case_dir=case_dir,
            backend_url="http://127.0.0.1:8000",
            runtime_version="fixture-runtime@1",
            labels_zip=labels_zip,
            expected_labels_zip_sha256=hashlib.sha256(labels_zip.read_bytes()).hexdigest(),
            timeout_seconds=5,
        )

    assert not (case_dir / "frozen_label.json").exists()


def test_phase_b_runner_checks_blind_label_zip_hash_before_freeze(tmp_path, monkeypatch):
    case_dir, labels_zip = _case(tmp_path)
    _install_fake_backend(monkeypatch)

    with pytest.raises(BenchmarkContractError, match="ZIP SHA256 mismatch"):
        runner.run_phase_b(
            case_dir=case_dir,
            backend_url="http://127.0.0.1:8000",
            runtime_version="fixture-runtime@1",
            labels_zip=labels_zip,
            expected_labels_zip_sha256="0" * 64,
            timeout_seconds=5,
        )

    assert not (case_dir / "frozen_label.json").exists()
