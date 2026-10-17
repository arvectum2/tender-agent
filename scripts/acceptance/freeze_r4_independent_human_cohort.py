"""Atomically receive a WHOLE source-locked independent human cohort.

Never creates reviewer attestations, labels, trusted keys, SUT outputs, or
owner legal acceptance. All signed cases must be independently delivered.
The caller's published source-lock summary is an externally pinned Git asset.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from scripts.acceptance.freeze_r4_independent_human_gold import (
    accept_independent_submission,
)
from src.modules.benchmark_pipeline.contract import (
    canonical_json,
    canonical_sha256,
    write_artifact,
)
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    verify_cohort_lock,
)


def validate_full_cohort_enrollment(
    *,
    immutable_locks: list[dict],
    published_summary: dict,
    case_inputs: list[dict],
) -> dict[str, int]:
    """Fail BEFORE reading any labels if a case or source group is missing."""
    expected_hashes = published_summary.get("blind_lock_sha256")
    if not isinstance(expected_hashes, list) or len(expected_hashes) != len(immutable_locks):
        raise ValueError("Published immutable lock set incomplete")
    if [x.get("immutable_lock_sha256") for x in immutable_locks] != expected_hashes:
        raise ValueError("Submitted source-lock SHA differs from published external audit")
    for lock in immutable_locks:
        verify_cohort_lock(lock)
        if lock.get("bid_ready") is not False:
            raise ValueError("Source-only lock cannot grant bid readiness")
    totals = [x["case_count"] for x in immutable_locks]
    if totals != published_summary.get("blind_cohort_sizes"):
        raise ValueError("Published blind cohort sizes changed")
    expected = {
        "R4-BLIND-" + case["registry_number"]: i
        for i, lock in enumerate(immutable_locks)
        for case in lock["cases"]
    }
    number = published_summary.get("source_blind_cases_total")
    if len(expected) != sum(totals) or len(expected) != number:
        raise ValueError("Expected unique source-locked case count not proven")
    if not isinstance(case_inputs, list) or len(case_inputs) != number:
        raise ValueError("All signed cases are mandatory before cohort gold freeze")
    supplied = [item.get("case_id") for item in case_inputs]
    if len(set(supplied)) != len(supplied) or set(supplied) != set(expected):
        raise ValueError("Missing, duplicate or extraneous signed reviewer case")
    for item in case_inputs:
        if item.get("lock_index") != expected[item["case_id"]]:
            raise ValueError("Human labels mapped to wrong immutable holdout group")
    return {"case_count": number, "cohort_count": len(immutable_locks)}


def preflight_complete_human_cohort(
    *,
    immutable_locks: list[dict],
    published_summary: dict,
    case_inputs: list[dict],
    trusted_reviewer_roster: dict,
    frozen_at: str,
) -> dict:
    """Validate all real submissions in memory; return no SUT authorization."""
    enrollment = validate_full_cohort_enrollment(
        immutable_locks=immutable_locks,
        published_summary=published_summary,
        case_inputs=case_inputs,
    )
    evaluated = []
    for case in sorted(case_inputs, key=lambda c: c["case_id"]):
        submission = case.get("submission")
        if not isinstance(submission, dict):
            raise TypeError("Missing independent human signed submission for locked case")
        result = accept_independent_submission(
            bundle_dir=Path(case["evaluator_bundle_dir"]),
            original_source_root=Path(case["original_source_root"]),
            submission=submission,
            trusted_reviewer_roster=trusted_reviewer_roster,
            immutable_holdout_lock=immutable_locks[case["lock_index"]],
            frozen_at=frozen_at,
        )
        if result["frozen"]["case_id"] != case["case_id"]:
            raise ValueError("Signed human result does not match locked case identity")
        # Keep the ORIGINAL signed submission for independent future audit.
        # A human-attested SHA of just the unsigned discovery/truth is NOT
        # enough to re-verify Ed25519 years after the initial acceptance.
        evaluated.append({
            "case_id": case["case_id"],
            "signed_submission": submission,
            **result,
        })
    if len(evaluated) != enrollment["case_count"]:
        raise ValueError("Cannot partially freeze an independent blind cohort")
    hashes = [
        {
            "case_id": item["case_id"],
            "label_set_sha256": item["frozen"]["label_set_sha256"],
            "source_bundle_sha256": item["frozen"]["source_bundle_sha256"],
            "signed_submission_sha256": canonical_sha256(item["signed_submission"]),
        }
        for item in evaluated
    ]
    receipt = {
        "phase": "ALL_INDEPENDENT_EXTERNAL_GOLD_LABELS_FROZEN",
        "source_blind_cases_total": enrollment["case_count"],
        "source_cohort_locks_sha256": published_summary["blind_lock_sha256"],
        "frozen_at": frozen_at,
        "signed_case_label_receipts": hashes,
        "aggregate_label_set_sha256": canonical_sha256(hashes),
        "legal_expertise_authority_certified_by_this_tool": False,
        "owner_legal_go_granted": False,
        "sut_run_authorized_by_this_tool": False,
        "bid_ready": False,
    }
    return {"case_artifacts": evaluated, "cohort_receipt": receipt}


def write_complete_human_cohort(
    *,
    validated: dict,
    private_output: Path,
) -> dict:
    """Stage complete set, then one atomic directory rename; never overwrite."""
    if private_output.exists() or not private_output.parent.is_dir():
        raise ValueError("Cannot overwrite or implicitly create a cohort gold location")
    cases = validated["case_artifacts"]
    receipt = validated["cohort_receipt"]
    expected_ids = [x["case_id"] for x in receipt["signed_case_label_receipts"]]
    if len(cases) != len(expected_ids) or [x["case_id"] for x in cases] != expected_ids:
        raise ValueError("Complete preflight case receipt was changed before writing")
    if (
        receipt.get("phase") != "ALL_INDEPENDENT_EXTERNAL_GOLD_LABELS_FROZEN"
        or receipt.get("sut_run_authorized_by_this_tool") is not False
        or receipt.get("owner_legal_go_granted") is not False
        or receipt.get("bid_ready") is not False
        or receipt.get("source_blind_cases_total") != len(cases)
    ):
        raise ValueError("Validated cohort receipt cannot authorize SUT, bids or partial gold")
    if receipt.get("aggregate_label_set_sha256") != canonical_sha256(
        receipt["signed_case_label_receipts"]
    ):
        raise ValueError("Cohort label SHA ledger changed between preflight and write")
    for case, expected in zip(cases, receipt["signed_case_label_receipts"]):
        frozen = case["frozen"]
        signed = case.get("signed_submission")
        if not isinstance(signed, dict) or not isinstance(
            signed.get("external_human_reviewer_attestation"), dict
        ):
            raise TypeError("Verified human signed source submission is missing")
        if (
            signed.get("case_id") != case["case_id"]
            or signed.get("blind_discovery_label") != case["discovery"]
            or signed.get("blind_document_truth") != case["truth"]
            or canonical_sha256(signed) != expected["signed_submission_sha256"]
        ):
            raise ValueError("Original signed human submission changed after trusted preflight")
        if (
            frozen["case_id"] != case["case_id"]
            or case["discovery"]["case_id"] != case["case_id"]
            or case["truth"]["case_id"] != case["case_id"]
            or expected["label_set_sha256"] != frozen["label_set_sha256"]
            or expected["source_bundle_sha256"] != frozen["source_bundle_sha256"]
            or canonical_sha256(case["discovery"]) != frozen["discovery_label_sha256"]
            or canonical_sha256(case["truth"]) != frozen["document_truth_sha256"]
            or canonical_sha256({
                "discovery_label_sha256": frozen["discovery_label_sha256"],
                "document_truth_sha256": frozen["document_truth_sha256"],
            }) != frozen["label_set_sha256"]
        ):
            raise ValueError("Human gold changed after trusted preflight validation")
    with tempfile.TemporaryDirectory(prefix=".full-independent-gold-", dir=private_output.parent) as scratch:
        stage = Path(scratch)
        for case in cases:
            destination = stage / case["case_id"]
            destination.mkdir()
            write_artifact(
                destination / "blind_discovery_label.json",
                case["discovery"],
                "blind_discovery_label",
            )
            write_artifact(
                destination / "blind_document_truth.json",
                case["truth"],
                "blind_document_truth",
            )
            write_artifact(
                destination / "frozen_label.json",
                case["frozen"],
                "frozen_label",
            )
            # Source-only private evidence: intentionally NOT in Git/public
            # acceptance reports. This preserves Ed25519 signature provenance.
            (destination / "independent-human-signed-submission.json").write_bytes(
                canonical_json(case["signed_submission"]) + b"\n"
            )
        (stage / "full-cohort-freeze-receipt.json").write_text(
            json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf8",
        )
        if private_output.exists():
            raise ValueError("Another process already created cohort freeze directory")
        stage.rename(private_output)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--published-source-audit", type=Path, required=True)
    parser.add_argument("--private-cohort-intake-manifest", type=Path, required=True)
    parser.add_argument("--private-trusted-reviewer-roster", type=Path, required=True)
    parser.add_argument("--private-frozen-output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.private_frozen_output_dir.exists():
        raise ValueError("Existing source-only cohort gold directory must not be overwritten")
    published = json.loads(args.published_source_audit.read_text())
    manifest = json.loads(args.private_cohort_intake_manifest.read_text())
    if not isinstance(manifest.get("source_lock_paths"), list):
        raise TypeError("Require complete private source lock path list")
    locks = [
        json.loads(Path(p).read_text()) for p in manifest["source_lock_paths"]
    ]
    # Verify all 15 expected source-case identities against immutable published
    # hashes BEFORE opening a single external human-submission file.
    if not isinstance(manifest.get("cases"), list):
        raise TypeError("Require complete case records for signed external review")
    validate_full_cohort_enrollment(
        immutable_locks=locks,
        published_summary=published,
        case_inputs=manifest["cases"],
    )
    supplied = []
    for item in manifest["cases"]:
        if not isinstance(item, dict):
            raise TypeError("Invalid reviewer case intake entry")
        path = item.get("signed_submission_path")
        if not isinstance(path, str) or not path:
            raise ValueError("Independent signed human submissions not all provided")
        supplied.append({
            "case_id": item["case_id"],
            "lock_index": item["lock_index"],
            "evaluator_bundle_dir": item["evaluator_bundle_dir"],
            "original_source_root": item["original_source_root"],
            "submission": json.loads(Path(path).read_text("utf8")),
        })
    roster = json.loads(args.private_trusted_reviewer_roster.read_text("utf8"))
    checked = preflight_complete_human_cohort(
        immutable_locks=locks,
        published_summary=published,
        case_inputs=supplied,
        trusted_reviewer_roster=roster,
        frozen_at=datetime.now(UTC).isoformat(timespec="microseconds"),
    )
    receipt = write_complete_human_cohort(
        validated=checked,
        private_output=args.private_frozen_output_dir,
    )
    print("FULL_REAL_EXTERNAL_HUMAN_COHORT_FROZEN", receipt["source_blind_cases_total"])
    print("LEGAL_EXPERT_QUALIFICATIONS_STILL_REQUIRE_SEPARATE_OWNER_VERIFICATION")
    print("SUT_RUN_AUTHORIZED", False, "BID_READY", False)


if __name__ == "__main__":
    main()
