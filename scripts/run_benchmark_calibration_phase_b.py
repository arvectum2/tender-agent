#!/usr/bin/env python3
"""Run the local-only post-label half of a real benchmark calibration safely.

Expected order:

context-bound Phase A -> independent blind labels -> THIS SCRIPT

This runner imports/validates the two blind-label files, freezes them before any
Tender Agent analysis, executes or resumes the exact Phase A backend run, stores
the raw runtime response, applies the repository-owned audited normalizer, runs
the deterministic comparator/review routing, and packages the complete case for
Product Owner inspection.

It deliberately does not score supplier-relative discovery. The document-analysis
runtime used here is not the discovery/search SUT; normalized discovery therefore
stays UNCLEAR and a context-bound case becomes NOT_SCORABLE for discovery. Actual
discovery benchmarking belongs to DISCOVERY-QA-001 with a separately context-bound
search/ranking result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_benchmark_calibration_phase_a import assert_source_only_run  # noqa: E402
from scripts.run_macmini_autonomous_procurement import (  # noqa: E402
    BackendClient,
    E2EBlocked,
    _auth_credentials_from_env,
)
from src.modules.benchmark_pipeline import (  # noqa: E402
    BenchmarkContractError,
    build_sut_ref,
    canonical_sha256,
    compare_case,
    freeze_blind_labels,
    infer_runtime_produced_at,
    load_artifact,
    normalize_runtime_response,
    route_review,
    validate_artifact,
    validate_blind_label_consistency,
    verify_frozen_labels,
    verify_manifest_source_files,
    verify_sut_after_freeze,
    write_artifact,
)

_LABEL_FILES = ("blind_discovery_label.json", "blind_document_truth.json")
_ANALYSIS_EVENTS = {
    "analysis_started",
    "analysis_completed",
    "llm_analysis_started",
    "llm_analysis_completed",
    "stub_analysis_fallback",
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BenchmarkContractError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_labels_zip(
    *,
    case_dir: Path,
    labels_zip: Path,
    expected_sha256: str | None,
) -> str:
    payload = labels_zip.read_bytes()
    actual_zip_sha = _sha256_bytes(payload)
    if expected_sha256 and actual_zip_sha != expected_sha256.lower():
        raise BenchmarkContractError(
            f"blind-label ZIP SHA256 mismatch: expected {expected_sha256.lower()}, got {actual_zip_sha}"
        )

    with zipfile.ZipFile(labels_zip, "r") as archive:
        files = [item for item in archive.infolist() if not item.is_dir()]
        by_basename: dict[str, zipfile.ZipInfo] = {}
        unexpected: list[str] = []
        for item in files:
            parts = Path(item.filename).parts
            if item.filename.startswith("/") or ".." in parts:
                raise BenchmarkContractError(f"unsafe blind-label ZIP path: {item.filename}")
            basename = Path(item.filename).name
            if basename not in _LABEL_FILES:
                unexpected.append(item.filename)
                continue
            if basename in by_basename:
                raise BenchmarkContractError(f"duplicate blind-label artifact in ZIP: {basename}")
            by_basename[basename] = item
        if unexpected:
            raise BenchmarkContractError(
                "blind-label ZIP must contain only the two label artifacts; unexpected: "
                + ", ".join(sorted(unexpected))
            )
        missing = [name for name in _LABEL_FILES if name not in by_basename]
        if missing:
            raise BenchmarkContractError(
                "blind-label ZIP is missing required artifacts: " + ", ".join(missing)
            )

        for name in _LABEL_FILES:
            target = case_dir / name
            new_bytes = archive.read(by_basename[name])
            if target.exists() and target.read_bytes() != new_bytes:
                raise BenchmarkContractError(
                    f"refusing to replace an existing different blind-label artifact: {name}"
                )
            target.write_bytes(new_bytes)

    return actual_zip_sha


def _analysis_event_types(run_payload: dict[str, Any]) -> set[str]:
    return {
        str(item.get("event_type") or "")
        for item in run_payload.get("events") or []
        if isinstance(item, dict)
    }


def _run_has_analysis(run_payload: dict[str, Any]) -> bool:
    mode = str(run_payload.get("analysis_mode") or "not_started")
    if mode != "not_started" or run_payload.get("final_recommendation") is not None:
        return True
    return bool(_analysis_event_types(run_payload) & _ANALYSIS_EVENTS)


def _load_phase_a_run_id(case_dir: Path) -> str:
    phase_a = _read_json(case_dir / "phase-a-result.json")
    run_id = str(phase_a.get("run_id") or "").strip()
    if not run_id:
        raise BenchmarkContractError("phase-a-result.json does not contain run_id")
    return run_id


def _freeze_or_resume(
    *,
    case_dir: Path,
    evaluator: dict[str, Any],
    discovery: dict[str, Any],
    truth: dict[str, Any],
    run_before_freeze: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    freeze_path = case_dir / "frozen_label.json"
    if freeze_path.exists():
        freeze = load_artifact(freeze_path, "frozen_label")
        verify_frozen_labels(freeze, evaluator, discovery, truth)
        return freeze, False

    # This is the critical anti-circularity boundary. If analysis already exists,
    # there is no valid way to create a blind freeze retroactively.
    assert_source_only_run(run_before_freeze)
    freeze = freeze_blind_labels(evaluator, discovery, truth, frozen_at=_now_iso())
    write_artifact(freeze_path, freeze, "frozen_label")
    return freeze, True


def _persist_runtime_response(case_dir: Path, run_payload: dict[str, Any]) -> Path:
    path = case_dir / "sut_runtime_response.json"
    if path.exists():
        previous = _read_json(path)
        previous_run_id = str(previous.get("run_id") or "")
        current_run_id = str(run_payload.get("run_id") or "")
        if previous_run_id and current_run_id and previous_run_id != current_run_id:
            raise BenchmarkContractError("existing runtime response belongs to another run")
    _write_json(path, run_payload)
    return path


def _package_case(case_dir: Path) -> Path:
    output = case_dir.parent / f"{case_dir.name}-phase-b-artifacts.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(case_dir.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(case_dir).as_posix())
    return output


def run_phase_b(
    *,
    case_dir: Path,
    backend_url: str,
    runtime_version: str,
    labels_zip: Path | None,
    expected_labels_zip_sha256: str | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    if not case_dir.is_dir():
        raise BenchmarkContractError(f"case directory does not exist: {case_dir}")

    manifest = load_artifact(case_dir / "case_manifest.json", "case_manifest")
    evaluator = load_artifact(case_dir / "evaluator_bundle.json", "evaluator_bundle")
    verify_manifest_source_files(manifest, case_dir)
    if evaluator["case_manifest_sha256"] != canonical_sha256(manifest):
        raise BenchmarkContractError("evaluator bundle is not bound to current case manifest")

    labels_zip_sha = None
    if labels_zip is not None:
        labels_zip_sha = import_labels_zip(
            case_dir=case_dir,
            labels_zip=labels_zip,
            expected_sha256=expected_labels_zip_sha256,
        )
    elif expected_labels_zip_sha256 is not None:
        raise BenchmarkContractError("--labels-zip-sha256 requires --labels-zip")

    discovery = load_artifact(case_dir / "blind_discovery_label.json", "blind_discovery_label")
    truth = load_artifact(case_dir / "blind_document_truth.json", "blind_document_truth")
    validate_blind_label_consistency(evaluator, discovery, truth)

    run_id = _load_phase_a_run_id(case_dir)
    client = BackendClient(
        backend_url,
        timeout_seconds=timeout_seconds,
        basic_auth=_auth_credentials_from_env(),
    )
    run_before = client.get_run(run_id)
    freeze, created_freeze = _freeze_or_resume(
        case_dir=case_dir,
        evaluator=evaluator,
        discovery=discovery,
        truth=truth,
        run_before_freeze=run_before,
    )

    if not _run_has_analysis(run_before):
        client.analyze(run_id)
    run_after = client.get_run(run_id)
    if not _run_has_analysis(run_after):
        raise BenchmarkContractError("Tender Agent analyze call returned without analysis output/events")
    runtime_path = _persist_runtime_response(case_dir, run_after)

    produced_at = infer_runtime_produced_at(run_after)
    normalized, audit = normalize_runtime_response(
        runtime_response=run_after,
        case_id=manifest["case_id"],
        source_bundle_sha256=manifest["source_bundle_sha256"],
        discovery_label="UNCLEAR",
        ranking_delta=None,
    )
    normalized_path = case_dir / "normalized_sut_output.json"
    audit_path = case_dir / "normalization_audit.json"
    write_artifact(normalized_path, normalized, "normalized_sut_output")
    _write_json(audit_path, audit)

    sut_ref = build_sut_ref(
        normalized_output=normalized,
        freeze_receipt=freeze,
        runtime_version=runtime_version,
        runtime_response_ref=runtime_path.name,
        produced_at=produced_at,
        normalization_audit_ref=audit_path.name,
        normalization_audit_sha256=canonical_sha256(audit),
        discovery_context_sha256_at_generation=None,
        extra_artifact_refs={"backend_run_id": run_id},
    )
    verify_sut_after_freeze(sut_ref, normalized, freeze)
    write_artifact(case_dir / "tender_agent_output_ref.json", sut_ref, "tender_agent_output_ref")

    comparison = compare_case(
        discovery_label=discovery,
        document_truth=truth,
        evaluator_bundle=evaluator,
        freeze_receipt=freeze,
        sut_ref=sut_ref,
        sut_output=normalized,
        compared_at=_now_iso(),
    )
    write_artifact(case_dir / "comparison_result.json", comparison, "comparison_result")

    review = route_review(
        manifest,
        discovery,
        truth,
        freeze,
        comparison,
        confidence_threshold=0.80,
        updated_at=_now_iso(),
    )
    write_artifact(case_dir / "review_state.json", review, "review_state")

    archive = _package_case(case_dir)
    result = {
        "status": "BENCHMARK_CALIBRATION_PHASE_B_COMPLETE",
        "case_id": manifest["case_id"],
        "run_id": run_id,
        "runtime_version": runtime_version,
        "freeze_created_this_run": created_freeze,
        "label_set_sha256": freeze["label_set_sha256"],
        "labels_zip_sha256": labels_zip_sha,
        "runtime_produced_at": produced_at,
        "normalized_output_sha256": canonical_sha256(normalized),
        "normalization_audit_sha256": canonical_sha256(audit),
        "normalization_audit_counts": audit["counts"],
        "discovery": comparison["discovery"],
        "document": {
            key: comparison["document"][key]
            for key in ("tp", "fp", "fn", "abstention_matches", "unscored_extras", "precision", "recall", "f1")
        },
        "review_state": review["state"],
        "review_reasons": review["reasons"],
        "artifact_zip": str(archive),
        "artifact_zip_sha256": _sha256_file(archive),
        "next_action": "STOP. Return the result and complete artifact ZIP to the Product Owner.",
    }
    _write_json(case_dir / "phase-b-result.json", result)
    # Repackage once so phase-b-result.json itself is included, then update its
    # externally reported digest without trying to self-embed the archive digest.
    archive = _package_case(case_dir)
    result["artifact_zip_sha256"] = _sha256_file(archive)
    _write_json(case_dir / "phase-b-result.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", required=True)
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--runtime-version", required=True)
    parser.add_argument("--labels-zip", default=None)
    parser.add_argument("--labels-zip-sha256", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_phase_b(
            case_dir=Path(args.case_dir).expanduser().resolve(),
            backend_url=args.backend_url,
            runtime_version=str(args.runtime_version).strip(),
            labels_zip=(Path(args.labels_zip).expanduser().resolve() if args.labels_zip else None),
            expected_labels_zip_sha256=(
                str(args.labels_zip_sha256).strip().lower() if args.labels_zip_sha256 else None
            ),
            timeout_seconds=max(1, int(args.timeout_seconds)),
        )
    except (BenchmarkContractError, E2EBlocked, FileNotFoundError, json.JSONDecodeError) as exc:
        payload: dict[str, Any] = {
            "status": "BENCHMARK_CALIBRATION_PHASE_B_BLOCKED",
            "error": str(exc),
        }
        if isinstance(exc, E2EBlocked):
            payload["code"] = exc.code
            payload["details"] = exc.details
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
