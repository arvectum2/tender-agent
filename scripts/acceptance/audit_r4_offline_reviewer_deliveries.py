"""Re-audit transferred source-only reviewer ZIPs against external SHA/locks.

No outside reviewer is contacted, no model inference, no gold freeze or SUT.
The delivery receipt and original lock must come from trusted local originals.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.modules.tender_operator_agent_demo.r4_offline_reviewer_verifier import (
    verify_offline_reviewer_zip,
)
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    forbid_reuse_of_prior_blind_cohorts,
    forbidden_development_sources,
    verify_cohort_lock,
)


def verify_published_immutable_locks(locks: list[dict], published: dict) -> None:
    """Require the public preregistered SHA list, not just a self-hashed lock."""
    if [x["immutable_lock_sha256"] for x in locks] != published.get("blind_lock_sha256"):
        raise ValueError("Private blind lock digests differ from published preregistered audit")


def audit_group(lock: dict, receipt: dict, delivery_root: Path) -> dict:
    verify_cohort_lock(lock)
    if (
        receipt.get("case_count") != lock["case_count"]
        or receipt.get("source_only") is not True
        or receipt.get("reviewer_external_contact_done") is not False
        or receipt.get("expert_gold_received") != 0
        or receipt.get("sut_run_authorized") is not False
    ):
        raise ValueError("Private reviewer delivery receipt not source-only or wrong count")
    cases = receipt.get("packages")
    if not isinstance(cases, list) or len(cases) != lock["case_count"]:
        raise ValueError("Expected one separately attested archive per case")
    ids = [x["case_id"] for x in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate case entries in human reviewer delivery")
    actual_zip = {f.name for f in delivery_root.glob("*.zip")}
    expected_zip = {case + ".zip" for case in ids}
    if actual_zip != expected_zip:
        raise ValueError("Unexpected, missing or untracked reviewer ZIP in delivery")
    verified = [
        verify_offline_reviewer_zip(
            private_archive=delivery_root / (row["case_id"] + ".zip"),
            trusted_delivery_receipt=row,
            trusted_immutable_lock=lock,
        )
        for row in cases
    ]
    if len(verified) != lock["case_count"]:
        raise ValueError("Not every firstparty original document passed audit")
    return {
        "source_lock_sha256": lock["immutable_lock_sha256"],
        "case_count": len(verified),
        "original_count": sum(x["original_count"] for x in verified),
        "unsigned_source_only_archives_sha_verified": len(verified),
        "reviewer_responses_present": False,
        "signed_gold_cases": 0,
        "sut_run_authorized": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--private-lock", action="append", type=Path, required=True)
    p.add_argument("--private-receipt", action="append", type=Path, required=True)
    p.add_argument("--private-delivery-root", action="append", type=Path, required=True)
    p.add_argument("--development-audit", type=Path, required=True)
    p.add_argument("--published-immutable-cohort-summary", type=Path, required=True)
    p.add_argument("--private-output", type=Path, required=True)
    args = p.parse_args()
    if len(args.private_lock) != 4 or not (
        len(args.private_lock) == len(args.private_receipt) == len(args.private_delivery_root)
    ):
        raise ValueError("Exactly four original independent source-only groups are required")
    if args.private_output.exists():
        raise ValueError("Existing offline handoff audit may never be overwritten")
    locks = [json.loads(x.read_text()) for x in args.private_lock]
    published = json.loads(args.published_immutable_cohort_summary.read_text())
    verify_published_immutable_locks(locks, published)
    development = json.loads(args.development_audit.read_text())
    protected = forbid_reuse_of_prior_blind_cohorts(forbidden_development_sources(development), locks)
    result = [
        audit_group(lock, json.loads(receipt.read_text()), directory)
        for lock, receipt, directory in zip(
            locks, args.private_receipt, args.private_delivery_root
        )
    ]
    if (
        [x["case_count"] for x in result] != [3, 4, 4, 4]
        or [x["original_count"] for x in result] != [16, 21, 19, 17]
        or len(protected["notice_numbers"]) != 35
        or len(protected["binary_sha256"]) != 169
    ):
        raise ValueError("Offline delivery counts differ from full 15-case blind cohort")
    summary = {
        "status": "ALL_OFFLINE_ORIGINAL_PACKAGES_EXTERNALLY_SHA_AND_LOCK_VERIFIED",
        "blind_cases": sum(x["case_count"] for x in result),
        "original_documents": sum(x["original_count"] for x in result),
        "groups": result,
        "protected_development_and_blind_notices": len(protected["notice_numbers"]),
        "protected_original_sha256": len(protected["binary_sha256"]),
        "expert_contacted": False,
        "signed_independent_human_gold": 0,
        "sut_ran": False,
        "precision_recall": "NOT_MEASURED",
        "bid_ready": False,
    }
    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print("REVALIDATED_INDEPENDENT_BLIND_SOURCE_PACKAGES", summary["blind_cases"], "ORIGINAL_DOCUMENTS", summary["original_documents"])
    print("SIGNED_HUMAN_GOLD", 0, "SUT_RUN", False, "BID_READY", False)


if __name__ == "__main__":
    main()
