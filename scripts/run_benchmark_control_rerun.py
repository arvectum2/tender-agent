#!/usr/bin/env python3
"""Run a post-fix benchmark control against an existing frozen real case.

This helper is deliberately narrower than Phase A:

existing frozen case -> copy immutable truth/source artifacts -> acquire a fresh
source-only Tender Agent run -> verify the backend run has the exact same source
byte hashes -> run SUT analysis -> save raw runtime response -> STOP.

It never regenerates evaluator input, labels, or the freeze receipt. Normalization,
comparison, and review routing remain explicit repository-owned follow-up steps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_benchmark_calibration_phase_a import (  # noqa: E402
    _download_bytes,
    assert_source_only_run,
    select_exact_card,
    source_only_handoff,
)
from scripts.run_macmini_autonomous_procurement import (  # noqa: E402
    READY_STATUSES,
    BackendClient,
    E2EBlocked,
    _auth_credentials_from_env,
)
from src.modules.benchmark_pipeline import (  # noqa: E402
    BenchmarkContractError,
    canonical_sha256,
    load_artifact,
    verify_manifest_source_files,
)
from src.modules.benchmark_pipeline.workflow import verify_frozen_labels  # noqa: E402

IMMUTABLE_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("case_manifest.json", "case_manifest"),
    ("evaluator_bundle.json", "evaluator_bundle"),
    ("blind_discovery_label.json", "blind_discovery_label"),
    ("blind_document_truth.json", "blind_document_truth"),
    ("frozen_label.json", "frozen_label"),
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_file_digests(case_dir: Path) -> dict[str, str]:
    return {name: _sha256_file(case_dir / name) for name, _kind in IMMUTABLE_ARTIFACTS}


def _verify_frozen_case(
    *,
    manifest: dict[str, Any],
    evaluator: dict[str, Any],
    discovery: dict[str, Any],
    truth: dict[str, Any],
    freeze: dict[str, Any],
    case_dir: Path,
) -> None:
    try:
        verify_manifest_source_files(manifest, case_dir)
        verify_frozen_labels(freeze, evaluator, discovery, truth)
    except BenchmarkContractError as exc:
        raise E2EBlocked(
            "control_frozen_case_invalid",
            "Frozen benchmark inputs failed contract/hash verification.",
            details={"error": str(exc)},
        ) from exc
    if canonical_sha256(manifest) != freeze["case_manifest_sha256"]:
        raise E2EBlocked(
            "control_manifest_changed_after_freeze",
            "Case manifest does not match the manifest digest bound by the frozen label receipt.",
        )


def copy_frozen_case(source_case_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Copy only immutable benchmark inputs; never copy prior SUT/comparison artifacts."""

    if output_dir.exists() and any(output_dir.iterdir()):
        raise E2EBlocked(
            "control_output_directory_not_empty",
            "Benchmark control output directory must be new or empty.",
            details={"output_dir": str(output_dir)},
        )

    manifest = load_artifact(source_case_dir / "case_manifest.json", "case_manifest")
    evaluator = load_artifact(source_case_dir / "evaluator_bundle.json", "evaluator_bundle")
    discovery = load_artifact(
        source_case_dir / "blind_discovery_label.json", "blind_discovery_label"
    )
    truth = load_artifact(source_case_dir / "blind_document_truth.json", "blind_document_truth")
    freeze = load_artifact(source_case_dir / "frozen_label.json", "frozen_label")
    _verify_frozen_case(
        manifest=manifest,
        evaluator=evaluator,
        discovery=discovery,
        truth=truth,
        freeze=freeze,
        case_dir=source_case_dir,
    )
    before = _artifact_file_digests(source_case_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_case_dir / "source", output_dir / "source")
    for name, _kind in IMMUTABLE_ARTIFACTS:
        shutil.copy2(source_case_dir / name, output_dir / name)

    copied_manifest = load_artifact(output_dir / "case_manifest.json", "case_manifest")
    copied_evaluator = load_artifact(output_dir / "evaluator_bundle.json", "evaluator_bundle")
    copied_discovery = load_artifact(
        output_dir / "blind_discovery_label.json", "blind_discovery_label"
    )
    copied_truth = load_artifact(output_dir / "blind_document_truth.json", "blind_document_truth")
    copied_freeze = load_artifact(output_dir / "frozen_label.json", "frozen_label")
    _verify_frozen_case(
        manifest=copied_manifest,
        evaluator=copied_evaluator,
        discovery=copied_discovery,
        truth=copied_truth,
        freeze=copied_freeze,
        case_dir=output_dir,
    )
    after = _artifact_file_digests(output_dir)
    if before != after:
        raise E2EBlocked(
            "immutable_benchmark_copy_mismatch",
            "Frozen benchmark artifacts changed while preparing the control rerun.",
            details={"before": before, "after": after},
        )
    return copied_manifest


def expected_source_hashes(manifest: dict[str, Any]) -> Counter[str]:
    return Counter(str(item["sha256"]) for item in manifest.get("documents") or [])


def runtime_source_hashes(
    *,
    backend_url: str,
    run_id: str,
    run_payload: dict[str, Any],
    credentials: tuple[str, str] | None,
    timeout_seconds: int,
) -> Counter[str]:
    hashes: Counter[str] = Counter()
    for item in run_payload.get("files") or []:
        if not isinstance(item, dict):
            continue
        file_id = str(item.get("file_id") or "").strip()
        if not file_id:
            continue
        payload = _download_bytes(
            backend_url,
            f"/api/demo/tender-agent/runs/{run_id}/files/{file_id}/download",
            credentials=credentials,
            timeout_seconds=timeout_seconds,
        )
        hashes[hashlib.sha256(payload).hexdigest()] += 1
    return hashes


def assert_exact_source_hashes(
    *,
    manifest: dict[str, Any],
    observed: Counter[str],
) -> None:
    expected = expected_source_hashes(manifest)
    if expected == observed:
        return
    raise E2EBlocked(
        "control_source_bundle_mismatch",
        "Fresh backend run does not contain the exact frozen source-byte set. Analysis was not started.",
        details={
            "expected": dict(sorted(expected.items())),
            "observed": dict(sorted(observed.items())),
        },
    )


def run_control(
    *,
    source_case_dir: Path,
    output_dir: Path,
    backend_url: str,
    runtime_version: str,
    query: str | None,
    search_days: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    manifest = copy_frozen_case(source_case_dir, output_dir)
    procurement = manifest.get("procurement") or {}
    registry_number = str(
        procurement.get("notice_number") or procurement.get("registry_number") or ""
    ).strip()
    if not registry_number:
        raise E2EBlocked(
            "control_missing_registry_number",
            "Frozen benchmark manifest has no procurement registry number.",
        )

    credentials = _auth_credentials_from_env()
    client = BackendClient(
        backend_url,
        timeout_seconds=timeout_seconds,
        basic_auth=credentials,
    )
    today = date.today()
    search = client.search(
        query=query or registry_number,
        law="44fz",
        max_results=50,
        date_from=(today - timedelta(days=search_days)).isoformat(),
        date_to=today.isoformat(),
    )
    cards = search.get("cards") or []
    if not isinstance(cards, list):
        raise E2EBlocked(
            "control_search_invalid_shape",
            "Public 44-FZ search returned a non-list cards field.",
        )
    card = select_exact_card(cards, registry_number)

    handoff = source_only_handoff(client, card=card, registry_number=registry_number)
    run_id = str(handoff.get("run_id") or "").strip()
    if not run_id:
        raise E2EBlocked("control_missing_run_id", "Source-only handoff returned no run_id.")

    pre_analysis = client.get_run(run_id)
    assert_source_only_run(pre_analysis)
    observed = runtime_source_hashes(
        backend_url=backend_url,
        run_id=run_id,
        run_payload=pre_analysis,
        credentials=credentials,
        timeout_seconds=timeout_seconds,
    )
    assert_exact_source_hashes(manifest=manifest, observed=observed)

    client.analyze(run_id)
    runtime = client.get_run(run_id)
    status = str(runtime.get("status") or "")
    if status not in READY_STATUSES:
        raise E2EBlocked(
            "control_analysis_not_ready",
            "Tender Agent analysis did not finish in a benchmark-ready state.",
            details={"run_id": run_id, "status": status},
        )
    _write_json(output_dir / "sut_runtime_response.json", runtime)

    result = {
        "status": "BENCHMARK_CONTROL_RUNTIME_READY",
        "case_id": manifest["case_id"],
        "registry_number": registry_number,
        "runtime_version": runtime_version,
        "run_id": run_id,
        "source_bundle_sha256": manifest["source_bundle_sha256"],
        "frozen_label_sha256": canonical_sha256(
            load_artifact(output_dir / "frozen_label.json", "frozen_label")
        ),
        "immutable_artifact_file_sha256": _artifact_file_digests(output_dir),
        "observed_source_hashes": dict(sorted(observed.items())),
        "output_dir": str(output_dir),
        "runtime_response": str(output_dir / "sut_runtime_response.json"),
        "completed_at": _now_iso(),
        "next_action": (
            "Run repository-owned normalize-phase-b, compare, and route-review in this control directory. "
            "Do not edit or regenerate labels/freeze."
        ),
    }
    _write_json(output_dir / "control-rerun-result.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-case-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--runtime-version", required=True)
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--query", default=None)
    parser.add_argument("--search-days", type=int, default=120)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_control(
            source_case_dir=Path(args.source_case_dir).expanduser().resolve(),
            output_dir=Path(args.output_dir).expanduser().resolve(),
            backend_url=args.backend_url,
            runtime_version=str(args.runtime_version),
            query=args.query,
            search_days=max(1, int(args.search_days)),
            timeout_seconds=max(1, int(args.timeout_seconds)),
        )
    except (E2EBlocked, BenchmarkContractError, FileNotFoundError, json.JSONDecodeError) as exc:
        if isinstance(exc, E2EBlocked):
            payload = {
                "status": "BENCHMARK_CONTROL_BLOCKED",
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        else:
            payload = {
                "status": "BENCHMARK_CONTROL_BLOCKED",
                "code": "control_input_error",
                "message": str(exc),
                "details": {},
            }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
