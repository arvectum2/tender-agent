#!/usr/bin/env python3
"""Calibration-only helpers for BENCHMARK-PIPELINE-001 real cases.

This CLI closes two gaps found by the first real 44-FZ Phase B run:

* bind immutable supplier/query discovery semantics before blind evaluation;
* normalize the real Tender Agent response with an audited, fail-closed projector.

It does not acquire procurements, run Tender Agent analysis, freeze labels, compare
cases, or promote review state. Those remain separate pipeline steps.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.benchmark_pipeline.calibration import (  # noqa: E402
    bind_discovery_context,
    build_discovery_context,
    build_sut_ref,
    discovery_context_sha256,
    infer_runtime_produced_at,
    normalize_runtime_response,
)
from src.modules.benchmark_pipeline.contract import (  # noqa: E402
    BenchmarkContractError,
    canonical_sha256,
    load_artifact,
    verify_manifest_source_files,
    write_artifact,
)
from src.modules.benchmark_pipeline.workflow import (  # noqa: E402
    prepare_evaluator_bundle,
    verify_sut_after_freeze,
)


_PRE_LABEL_FORBIDDEN = {
    "blind_discovery_label.json",
    "blind_document_truth.json",
    "frozen_label.json",
    "sut_runtime_response.json",
    "normalized_sut_output.json",
    "tender_agent_output_ref.json",
    "comparison_result.json",
    "review_state.json",
}
_DISCOVERY_LABELS = {"RELEVANT", "PARTIALLY_RELEVANT", "IRRELEVANT", "UNCLEAR"}


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


def _write_evaluator_zip(case_dir: Path) -> Path:
    output = case_dir.parent / f"{case_dir.name}-blind-evaluator-input.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for fixed in ("case_manifest.json", "evaluator_bundle.json"):
            archive.write(case_dir / fixed, arcname=fixed)
        for path in sorted((case_dir / "source").rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(case_dir).as_posix())
    return output


def bind_context_command(args: argparse.Namespace) -> dict[str, Any]:
    case_dir = Path(args.case_dir).expanduser().resolve()
    present = sorted(name for name in _PRE_LABEL_FORBIDDEN if (case_dir / name).exists())
    if present:
        raise BenchmarkContractError(
            "discovery context must be bound before blind labels/freeze/SUT; found: "
            + ", ".join(present)
        )

    manifest_path = case_dir / "case_manifest.json"
    manifest = load_artifact(manifest_path, "case_manifest")
    verify_manifest_source_files(manifest, case_dir)
    profile = _read_json(Path(args.supplier_profile).expanduser().resolve())

    if args.case_id:
        manifest = dict(manifest)
        manifest["case_id"] = args.case_id

    procurement = manifest.get("procurement") or {}
    registry_number = str(
        args.registry_number
        or procurement.get("notice_number")
        or procurement.get("registry_number")
        or ""
    ).strip()
    source = str(procurement.get("source") or "public_eis_html_44fz")
    law = str(procurement.get("law") or "44-ФЗ")
    context = build_discovery_context(
        supplier_profile=profile,
        registry_number=registry_number,
        source=source,
        law=law,
        as_of=args.as_of or manifest["acquired_at"],
        query=args.query,
    )
    bound = bind_discovery_context(manifest, context)
    write_artifact(manifest_path, bound, "case_manifest")
    evaluator = prepare_evaluator_bundle(bound)
    write_artifact(case_dir / "evaluator_bundle.json", evaluator, "evaluator_bundle")
    evaluator_zip = _write_evaluator_zip(case_dir)

    phase_a_result_path = case_dir / "phase-a-result.json"
    if phase_a_result_path.exists():
        phase_a_result = _read_json(phase_a_result_path)
        phase_a_result["case_id"] = bound["case_id"]
        phase_a_result["evaluator_zip"] = str(evaluator_zip)
        phase_a_result["discovery_context_sha256"] = discovery_context_sha256(bound)
        phase_a_result["next_action"] = (
            "STOP. Provide the context-bound evaluator ZIP to the independent evaluator. "
            "Do not freeze labels or run Tender Agent analysis yet."
        )
        _write_json(phase_a_result_path, phase_a_result)

    return {
        "status": "BENCHMARK_DISCOVERY_CONTEXT_BOUND",
        "case_id": bound["case_id"],
        "discovery_context_sha256": discovery_context_sha256(bound),
        "case_manifest_sha256": canonical_sha256(bound),
        "evaluator_bundle_sha256": canonical_sha256(evaluator),
        "evaluator_zip": str(evaluator_zip),
        "next_action": "Send evaluator ZIP for blind labels before freeze/SUT.",
    }


def _load_discovery_result(
    path: Path,
    *,
    evaluator_bundle: dict[str, Any],
) -> tuple[str, float | None, str]:
    payload = _read_json(path)
    label = str(payload.get("label") or "")
    if label not in _DISCOVERY_LABELS:
        raise BenchmarkContractError("discovery result has invalid label")
    expected = discovery_context_sha256(evaluator_bundle)
    if expected is None:
        raise BenchmarkContractError("evaluator bundle has no frozen discovery context")
    actual = str(payload.get("discovery_context_sha256") or "")
    if actual != expected:
        raise BenchmarkContractError("discovery result was produced under a different context")
    ranking_delta = payload.get("ranking_delta")
    if ranking_delta is not None and not isinstance(ranking_delta, (int, float)):
        raise BenchmarkContractError("discovery result ranking_delta must be numeric or null")
    return label, float(ranking_delta) if ranking_delta is not None else None, expected


def normalize_phase_b_command(args: argparse.Namespace) -> dict[str, Any]:
    case_dir = Path(args.case_dir).expanduser().resolve()
    manifest = load_artifact(case_dir / "case_manifest.json", "case_manifest")
    evaluator_bundle = load_artifact(case_dir / "evaluator_bundle.json", "evaluator_bundle")
    freeze = load_artifact(case_dir / "frozen_label.json", "frozen_label")
    runtime_path = Path(args.runtime_response).expanduser().resolve() if args.runtime_response else (
        case_dir / "sut_runtime_response.json"
    )
    runtime = _read_json(runtime_path)

    discovery_label = "UNCLEAR"
    ranking_delta = None
    bound_context_hash = None
    if args.discovery_result:
        discovery_label, ranking_delta, bound_context_hash = _load_discovery_result(
            Path(args.discovery_result).expanduser().resolve(),
            evaluator_bundle=evaluator_bundle,
        )

    output, audit = normalize_runtime_response(
        runtime_response=runtime,
        case_id=manifest["case_id"],
        source_bundle_sha256=manifest["source_bundle_sha256"],
        discovery_label=discovery_label,
        ranking_delta=ranking_delta,
    )
    audit_path = case_dir / "normalization_audit.json"
    _write_json(audit_path, audit)
    output_path = case_dir / "normalized_sut_output.json"
    write_artifact(output_path, output, "normalized_sut_output")

    produced_at = args.produced_at or infer_runtime_produced_at(runtime)
    extra_refs: dict[str, str] = {}
    if runtime.get("run_id"):
        extra_refs["backend_run_id"] = str(runtime["run_id"])
    ref = build_sut_ref(
        normalized_output=output,
        freeze_receipt=freeze,
        runtime_version=args.runtime_version,
        runtime_response_ref=runtime_path.name,
        produced_at=produced_at,
        normalization_audit_ref=audit_path.name,
        normalization_audit_sha256=canonical_sha256(audit),
        discovery_context_sha256_at_generation=bound_context_hash,
        extra_artifact_refs=extra_refs,
    )
    verify_sut_after_freeze(ref, output, freeze)
    write_artifact(case_dir / "tender_agent_output_ref.json", ref, "tender_agent_output_ref")

    return {
        "status": "BENCHMARK_PHASE_B_NORMALIZED",
        "case_id": manifest["case_id"],
        "discovery_label": discovery_label,
        "discovery_scorable": bound_context_hash is not None,
        "normalized_fact_count": len(output["facts"]),
        "normalization_audit_counts": audit["counts"],
        "normalized_output_sha256": canonical_sha256(output),
        "produced_at": produced_at,
        "next_action": "Run benchmark comparator and review routing against these first-party artifacts.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    bind = sub.add_parser("bind-context", help="Bind discovery semantics before blind evaluation.")
    bind.add_argument("--case-dir", required=True)
    bind.add_argument("--supplier-profile", required=True)
    bind.add_argument("--case-id", default=None)
    bind.add_argument("--registry-number", default=None)
    bind.add_argument("--query", default=None)
    bind.add_argument("--as-of", default=None)
    bind.set_defaults(handler=bind_context_command)

    normalize = sub.add_parser(
        "normalize-phase-b",
        help="Normalize a real post-freeze Tender Agent response with coverage audit.",
    )
    normalize.add_argument("--case-dir", required=True)
    normalize.add_argument("--runtime-response", default=None)
    normalize.add_argument("--runtime-version", required=True)
    normalize.add_argument("--produced-at", default=None)
    normalize.add_argument(
        "--discovery-result",
        default=None,
        help=(
            "Optional JSON from a context-bound discovery/search SUT. If omitted, discovery is "
            "normalized as UNCLEAR and remains unscored for a context-bound case."
        ),
    )
    normalize.set_defaults(handler=normalize_phase_b_command)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = args.handler(args)
    except (BenchmarkContractError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {"status": "BENCHMARK_CALIBRATION_BLOCKED", "error": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
