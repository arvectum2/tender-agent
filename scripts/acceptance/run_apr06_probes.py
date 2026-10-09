#!/usr/bin/env python3
"""APR-06 read-only 44-FZ probe runner with immutable, resumable case artifacts.

This is NOT the commercial acceptance scorer and it NEVER performs HUMAN,
ETP, payment, electronic-signature or submission actions. Candidate-only
sources are not auto-promoted to frozen/verified by this runner.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.modules.commercial_acceptance.acceptance import (
    AcceptanceError, _new_file, load_json, validate_manifest,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _public_probe(reg_number: str) -> dict:
    """Use the existing EIS SOAP getDocsIP document acquisition, no new stack."""
    from src.modules.tender_operator_agent_demo.procurement_intake_service import (
        create_run_from_eis_docs_archive,
    )
    from src.modules.tender_operator_agent_demo.schemas import EisDocsArchiveRunRequest

    response = create_run_from_eis_docs_archive(EisDocsArchiveRunRequest(
        reestr_number=reg_number, law="44fz", subsystem_type="PRIZ",
        method="getDocsByReestrNumber", download_archive=True,
        analyze_after_download=False,
    ))
    return {
        "run_id": response.run_id,
        "run_status": str(getattr(response.status, "value", response.status)),
        "downloaded_files_count": response.downloaded_files_count,
        "eis_reference": reg_number,
        "external_action_allowed": False,
    }


def _analyze_bound_run(run_id: str) -> dict:
    from src.modules.tender_operator_agent_demo.upload_service import (
        analyze_uploaded_demo_run,
    )

    response = analyze_uploaded_demo_run(run_id)
    return {
        "run_id": run_id,
        "analysis_status": str(getattr(response.status, "value", response.status)),
        "human_control_required": True,
        "external_action_allowed": False,
    }


def probe_one(case: dict, output_root: Path, *, execute: bool) -> dict:
    reg = case["reg_number"]
    if case["law"] != "44fz":
        return {"reg_number": reg, "stage": "UNSUPPORTED_223FZ_SOAP_ROUTING",
                "note": "Do not assume 44-FZ getDocsIP supports 223-FZ"}
    root = output_root / reg
    source_path = root / "source.json"
    analysis_path = root / "analysis.json"
    if not execute:
        return {"reg_number": reg, "stage": "DRY_RUN_READONLY_PROBE"}
    if not source_path.is_file():
        try:
            payload = _public_probe(reg)
            if payload["downloaded_files_count"] < 1:
                raise AcceptanceError(f"{reg}: no actual downloaded document")
            payload.update({
                "reg_number": reg, "schema_version": "apr06-probe-source-v1",
                "created_at": _now(), "operator_decision": None,
                "verified_eis_document_hashes": False,
            })
            _new_file(source_path, payload)
        except Exception as exc:
            return {"reg_number": reg, "stage": "INTAKE_FAILED",
                    "error_type": type(exc).__name__,
                    "eis_verified": False}
    saved = load_json(source_path)
    if saved.get("reg_number") != reg or saved.get("external_action_allowed") is not False:
        raise AcceptanceError(f"{reg}: invalid/tampered previous source checkpoint")
    if analysis_path.is_file():
        prior = load_json(analysis_path)
        if prior.get("reg_number") != reg or prior.get("run_id") != saved.get("run_id"):
            raise AcceptanceError(f"{reg}: analysis checkpoint run mismatch")
        return {"reg_number": reg, "stage": "REUSED_CHECKPOINT",
                "run_id": saved["run_id"], "analysis_status": prior["analysis_status"]}
    try:
        result = _analyze_bound_run(saved["run_id"])
        result.update({
            "reg_number": reg, "schema_version": "apr06-probe-analysis-v1",
            "created_at": _now(), "needs_human_review": True,
        })
        _new_file(analysis_path, result)
    except Exception as exc:
        return {"reg_number": reg, "stage": "ANALYSIS_FAILED",
                "run_id": saved["run_id"], "error_type": type(exc).__name__}
    return {"reg_number": reg, "stage": "HUMAN_REVIEW_PENDING",
            "run_id": saved["run_id"], "analysis_status": result["analysis_status"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="APR-06 local read-only EIS probe")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-cases", type=int, default=5)
    parser.add_argument("--execute-readonly", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.max_cases <= 30:
            raise AcceptanceError("max-cases must be between 1 and 30")
        manifest = load_json(args.manifest)
        validate_manifest(manifest)
        if args.output_dir.is_symlink():
            raise AcceptanceError("Output directory symlinks are forbidden")
        result = [
            probe_one(case, args.output_dir, execute=args.execute_readonly)
            for case in manifest["cases"][:args.max_cases]
        ]
        report = {"schema_version": "apr06-probes-v1", "executed": args.execute_readonly,
                  "cases": result, "submitted_bids": 0, "human_reviews_collected": 0,
                  "acceptance_completed": False}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.execute_readonly and any(x["stage"] in {
            "INTAKE_FAILED", "ANALYSIS_FAILED", "UNSUPPORTED_223FZ_SOAP_ROUTING"
        } for x in result):
            return 2
        return 0
    except AcceptanceError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
