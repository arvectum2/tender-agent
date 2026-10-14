"""Select discoverable source IDs by preregistered rank, never model output.

Inputs are opaque, independently fetched page snapshots. Without a complete,
current and verifiable snapshot from ALL pinned feeds this tool will refuse
selection. getDocsIP + raw attachments must be verified in a separate stage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.modules.tender_operator_agent_demo.r4_prospective_sampling import (
    select_source_only_candidates,
    validate_sampling_intent,
)
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    forbid_reuse_of_prior_blind_cohorts,
    forbidden_development_sources,
    verify_cohort_lock,
)


def select_officially_unverified_candidates(
    *,
    selection_intent: dict,
    current_private_snapshots: list[dict],
    development_audit: dict,
    earlier_blind_lock: dict,
) -> dict:
    """Validate both immutable locks before accepting any discovery ID."""
    validate_sampling_intent(selection_intent)
    verify_cohort_lock(earlier_blind_lock)
    if selection_intent["prior_blind_lock_sha256"] != earlier_blind_lock["immutable_lock_sha256"]:
        raise ValueError("Source plan references a different earlier blind cohort")
    seen = forbid_reuse_of_prior_blind_cohorts(
        forbidden_development_sources(development_audit),
        [earlier_blind_lock],
    )
    return select_source_only_candidates(
        intent=selection_intent,
        snapshots=current_private_snapshots,
        forbidden_numbers=seen["notice_numbers"],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registered-intent", type=Path, required=True)
    parser.add_argument("--live-verified-snapshots", type=Path, required=True)
    parser.add_argument("--development-audit", type=Path, required=True)
    parser.add_argument("--prior-blind-lock", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args()
    if args.private_output.exists():
        raise ValueError("Do not silently replace an immutable candidate discovery receipt")
    intent = json.loads(args.registered_intent.read_text())
    snapshots = json.loads(args.live_verified_snapshots.read_text())
    historic = json.loads(args.development_audit.read_text())
    earlier = json.loads(args.prior_blind_lock.read_text())
    report = select_officially_unverified_candidates(
        selection_intent=intent,
        current_private_snapshots=snapshots,
        development_audit=historic,
        earlier_blind_lock=earlier,
    )
    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8",
    )
    print(
        "DISCOVERY_IDS_ONLY_NOT_REAL_VERIFIED_COHORT",
        len(report["discovery_candidate_numbers"]),
        report["selection_status"],
    )


if __name__ == "__main__":
    main()
