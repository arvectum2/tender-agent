"""Generate a PRIVATE zero-label input inventory for complete external R4 gold.

Source-only inventory: 15 unsigned expert submissions required. Never writes
reviewer answers, signatures, keys, credentials, SUT outputs or frozen gold.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.modules.benchmark_pipeline.contract import (
    canonical_sha256,
    load_artifact,
    verify_manifest_source_files,
)
from src.modules.benchmark_pipeline.workflow import assert_blind_evaluator_bundle
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    verify_cohort_lock,
)


def build_empty_cohort_intake_manifest(
    *,
    public_immutable_summary: dict,
    source_lock_paths: list[Path],
    evaluator_roots: list[Path],
    original_source_roots: list[Path],
) -> dict:
    if len(source_lock_paths) != len(evaluator_roots) or len(source_lock_paths) != len(
        original_source_roots
    ):
        raise ValueError("Each blind group requires its own lock, evaluator and original source")
    if len(source_lock_paths) != len(public_immutable_summary.get("blind_lock_sha256", [])):
        raise ValueError("Not every publicly registered source lock supplied")
    results = []
    locks = []
    for i, (source, pack_root, raw_root) in enumerate(
        zip(source_lock_paths, evaluator_roots, original_source_roots)
    ):
        locked = json.loads(source.read_text("utf8"))
        verify_cohort_lock(locked)
        if locked["immutable_lock_sha256"] != public_immutable_summary["blind_lock_sha256"][i]:
            raise ValueError("Private source lock differs from published SHA")
        if locked["case_count"] != len(locked["cases"]):
            raise ValueError("Original-source lock case count changed")
        expected_case_ids = {
            "R4-BLIND-" + item["registry_number"]: item
            for item in locked["cases"]
        }
        discovered = sorted(pack_root.glob("*/evaluator_bundle.json"))
        if len(discovered) != locked["case_count"]:
            raise ValueError("Missing or extra evaluator bundles relative to locked source cases")
        if {x.parent.name for x in discovered} != set(expected_case_ids):
            raise ValueError("Evaluator case IDs do not match immutable source lock")
        for artifact_path in discovered:
            bundle_dir = artifact_path.parent
            bundle = load_artifact(artifact_path, "evaluator_bundle")
            manifest = load_artifact(bundle_dir / "case_manifest.json", "case_manifest")
            assert_blind_evaluator_bundle(bundle)
            case_id = bundle["case_id"]
            if manifest["case_id"] != case_id or bundle_dir.name != case_id:
                raise ValueError("Inconsistent source bundle case identity")
            if bundle["case_manifest_sha256"] != canonical_sha256(manifest):
                raise ValueError("Locked case manifest SHA changed after evaluator bundle")
            expected = expected_case_ids[case_id]["original_attachment_sha256"]
            if sorted(x["sha256"] for x in bundle["documents"]) != sorted(expected):
                raise ValueError("Original binary SHA differs from protected source lock")
            verify_manifest_source_files(manifest, raw_root)
            results.append({
                "case_id": case_id,
                "lock_index": i,
                "evaluator_bundle_dir": str(bundle_dir.resolve()),
                "original_source_root": str(raw_root.resolve()),
                "signed_submission_path": None,
            })
        locks.append(locked)
    if [lock["case_count"] for lock in locks] != public_immutable_summary["blind_cohort_sizes"]:
        raise ValueError("Cohort size no longer matches published blind protocol")
    if len(results) != public_immutable_summary["source_blind_cases_total"]:
        raise ValueError("Full blind cohort input set is incomplete")
    if len({x["case_id"] for x in results}) != len(results):
        raise ValueError("Duplicate source-only case across intake groups")
    return {
        "status": "AWAITING_INDEPENDENT_HUMAN_REVIEWER_SIGNED_SUBMISSIONS",
        "source_lock_paths": [str(p.resolve()) for p in source_lock_paths],
        "published_lock_sha256": public_immutable_summary["blind_lock_sha256"],
        "case_count": len(results),
        "signed_case_count": 0,
        "trusted_public_reviewer_keys_supplied": False,
        "sut_run_authorized": False,
        "bid_ready": False,
        "cases": sorted(results, key=lambda x: x["case_id"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--published-source-audit", type=Path, required=True)
    parser.add_argument("--immutable-lock", type=Path, action="append", required=True)
    parser.add_argument("--evaluator-root", type=Path, action="append", required=True)
    parser.add_argument("--original-source-root", type=Path, action="append", required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args()
    if args.private_output.exists():
        raise ValueError("Existing private intake manifest cannot be overwritten")
    expected = json.loads(args.published_source_audit.read_text())
    result = build_empty_cohort_intake_manifest(
        public_immutable_summary=expected,
        source_lock_paths=args.immutable_lock,
        evaluator_roots=args.evaluator_root,
        original_source_roots=args.original_source_root,
    )
    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf8",
    )
    print("PREPARED_EMPTY_INDEPENDENT_LEGAL_GOLD_INTAKE",result["case_count"],"CASES")
    print("INDEPENDENT_EXPERT_SIGNED_GOLD",0,"SUT_RUN_AUTHORIZED",False)


if __name__ == "__main__":
    main()
