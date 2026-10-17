"""Evaluate a DEVELOPMENT-only operator E2E receipt, not a legal bid decision.

Owner-delegated ChatGPT source review is sufficient for THIS developmental
acceptance; an externally signed human-gold cohort is not an input. Assertions
still require independent runtime/source proof, never self-awarded AI opinions.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_RUN_ID = re.compile(r"toa-run-[0-9]{14}-[a-f0-9]{6,16}\Z")
_REQUIRED = (
    "search",
    "source_download",
    "document_extraction",
    "model_analysis",
    "cited_report",
    "history_reopen",
    "registry_readonly",
    "export_safety",
)


def evaluate(receipt: dict[str, Any]) -> dict[str, Any]:
    """Return fail-closed evidence findings; acceptance has NO bid authority."""
    reasons: list[str] = []
    if receipt.get("stage") != "development_e2e":
        reasons.append("wrong_stage")
    if receipt.get("reviewer_kind") != "owner_delegated_chatgpt":
        reasons.append("missing_owner_delegated_ai_review")
    if receipt.get("reviewer_source_facts_checked") is not True:
        reasons.append("expert_source_review_not_attested")
    if not re.fullmatch(r"(?:\d{19}|\d{11})", str(receipt.get("notice_number", ""))):
        reasons.append("invalid_notice_number")
    if not _RUN_ID.fullmatch(str(receipt.get("run_id", ""))):
        reasons.append("missing_real_run_identity")
    if not _SHA256.fullmatch(str(receipt.get("report_sha256", ""))):
        reasons.append("missing_report_hash")
    sources = receipt.get("official_originals")
    if not isinstance(sources, list) or not sources:
        reasons.append("missing_original_source_files")
    else:
        for source in sources:
            if not isinstance(source, dict) or (
                not _SHA256.fullmatch(str(source.get("sha256", "")))
                or not source.get("original_name")
                or source.get("verified_from_official") is not True
            ):
                reasons.append("unverified_original_source")
                break
    steps = receipt.get("steps")
    if not isinstance(steps, dict):
        steps = {}
    for step in _REQUIRED:
        evidence = steps.get(step)
        if not isinstance(evidence, dict) or evidence.get("passed") is not True or not evidence.get("evidence_ref"):
            reasons.append(f"e2e_step_not_proven:{step}")
    citations = receipt.get("citation_audit")
    if not isinstance(citations, dict):
        citations = {}
    if (
        type(citations.get("verified_fact_claims")) is not int
        or citations.get("verified_fact_claims", 0) < 1
        or type(citations.get("unsupported_material_claims")) is not int
        or citations.get("unsupported_material_claims") != 0
    ):
        reasons.append("material_claim_citations_not_verified")
    if receipt.get("analysis_mode") != "llm_tender_operator_provider":
        reasons.append("full_model_analysis_not_proven")
    if (
        receipt.get("current_official_revision_verified") is not True
        and receipt.get("archival_export_http_status") != 409
    ):
        # A historical notice must not produce an official-style export.
        reasons.append("archival_export_fail_closed_not_proven")
    if receipt.get("critical_workflow_defects") != 0:
        reasons.append("critical_workflow_defects_open")
    prohibited = (
        "bid_submitted",
        "digital_signature_used",
        "payment_created",
        "production_mutated",
        "etp_mutated",
        "owner_legal_go_granted",
    )
    if any(receipt.get(key) is not False for key in prohibited):
        reasons.append("procurement_or_production_boundary_not_proven")
    return {
        "stage": "development_e2e",
        "accepted": not reasons,
        "reviewer_kind": "owner_delegated_chatgpt",
        "not_a_human_gold_label": True,
        "grants_bid_authority": False,
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        document = json.loads(args.receipt.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise TypeError("receipt must be a JSON object")
        result = evaluate(document)
    except (TypeError, ValueError, OSError) as exc:
        result = {
            "stage": "development_e2e",
            "accepted": False,
            "not_a_human_gold_label": True,
            "grants_bid_authority": False,
            "reasons": [f"invalid_receipt:{type(exc).__name__}"],
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
