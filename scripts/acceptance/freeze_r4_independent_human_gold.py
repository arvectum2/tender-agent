"""Receive owner-trusted, externally signed human gold; never create labels.

This does not establish a lawyer's qualification. The owner must independently
verify reviewer identity and public key OUTSIDE the project before this tool.
A failed validation never writes a frozen-label receipt or authorizes SUT.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from src.modules.benchmark_pipeline.contract import load_artifact, write_artifact
from src.modules.tender_operator_agent_demo.r4_external_gold_intake import (
    freeze_verified_external_gold,
)
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    verify_cohort_lock,
)


def accept_independent_submission(
    *, bundle_dir: Path,
    original_source_root: Path,
    submission: dict,
    trusted_reviewer_roster: dict,
    immutable_holdout_lock: dict,
    frozen_at: str,
) -> dict:
    """In-memory fail-closed freeze; only caller writes after full validation."""
    if submission.get("draft_status") != "EXPERT_SUBMITTED":
        raise ValueError("Blank/draft labels must never be treated as verified human gold")
    if submission.get("sut_inference_allowed") is not False:
        raise ValueError("SUT exposure is prohibited until gold freeze")
    bundle = load_artifact(bundle_dir / "evaluator_bundle.json", "evaluator_bundle")
    manifest = load_artifact(bundle_dir / "case_manifest.json", "case_manifest")
    verify_cohort_lock(immutable_holdout_lock)
    matches = [
        case for case in immutable_holdout_lock["cases"]
        if case["registry_number"] == bundle["procurement"].get("notice_number")
    ]
    if len(matches) != 1 or sorted(matches[0]["original_attachment_sha256"]) != sorted(
        d["sha256"] for d in bundle["documents"]
    ):
        raise ValueError("Submitted human labels do not belong to immutable held-out sources")
    from datetime import datetime as _dt
    lock_at = _dt.fromisoformat(immutable_holdout_lock["locked_at_utc"])
    bundle_at = _dt.fromisoformat(bundle["prepared_at"])
    if lock_at.tzinfo is None or bundle_at.tzinfo is None or bundle_at < lock_at:
        raise ValueError("Held-out source set was not locked before evaluator bundle creation")
    if (
        submission.get("case_id") != bundle["case_id"] or
        submission.get("source_bundle_sha256") != bundle["source_bundle_sha256"]
    ):
        raise ValueError("External labels are for a different verified source bundle")
    discovery = submission["blind_discovery_label"]
    truth = submission["blind_document_truth"]
    signed = submission["external_human_reviewer_attestation"]
    freeze = freeze_verified_external_gold(
        evaluator_bundle=bundle,
        discovery_label=discovery,
        document_truth=truth,
        source_manifest=manifest,
        original_source_root=original_source_root,
        signed_attestation=signed,
        trusted_reviewer_keys=trusted_reviewer_roster,
        frozen_at=frozen_at,
    )
    return {"discovery": discovery, "truth": truth, "frozen": freeze}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluator-bundle-dir", type=Path, required=True)
    parser.add_argument("--private-source-root", type=Path, required=True)
    parser.add_argument("--human-submission", type=Path, required=True)
    parser.add_argument("--immutable-holdout-lock", type=Path, required=True)
    parser.add_argument("--owner-trusted-public-key-roster", type=Path, required=True)
    parser.add_argument("--frozen-output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.frozen_output_dir
    if output.exists():
        raise ValueError("Never overwrite a previously frozen independent gold set")
    if not output.parent.exists():
        raise ValueError("Private output parent must exist before freeze")
    submitted = json.loads(args.human_submission.read_text("utf8"))
    trusted = json.loads(args.owner_trusted_public_key_roster.read_text("utf8"))
    lock = json.loads(args.immutable_holdout_lock.read_text("utf8"))
    artifacts = accept_independent_submission(
        bundle_dir=args.evaluator_bundle_dir,
        original_source_root=args.private_source_root,
        submission=submitted,
        trusted_reviewer_roster=trusted,
        immutable_holdout_lock=lock,
        frozen_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    # Make all output visible at once; failed validation leaves no frozen files.
    with tempfile.TemporaryDirectory(prefix=".human-gold-validated-", dir=output.parent) as temp:
        tmp = Path(temp)
        write_artifact(tmp / "blind_discovery_label.json", artifacts["discovery"], "blind_discovery_label")
        write_artifact(tmp / "blind_document_truth.json", artifacts["truth"], "blind_document_truth")
        write_artifact(tmp / "frozen_label.json", artifacts["frozen"], "frozen_label")
        tmp.rename(output)
    print("HUMAN_GOLD_FROZEN_WITH_TRUSTED_EXTERNAL_REVIEWER", artifacts["frozen"]["case_id"])


if __name__ == "__main__":
    main()
