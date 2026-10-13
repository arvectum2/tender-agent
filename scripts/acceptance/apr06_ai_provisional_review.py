"""Conservative as-of screening of APR-06 *existing* archival AI evidence.

This is not EIS revalidation, legal expertise, a human observation, or a GO/NO_GO
participation decision. It must never write the commercial-acceptance observation
schema or inflate the frozen human-gold benchmark.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "docs/acceptance"
CANDIDATES = SOURCES / "apr06_candidate_pool_2026-10-09.json"
PRIOR_AUDIT = SOURCES / "apr06_independent_gpt6_audit_2026-10-09.json"
PREFILL = SOURCES / "apr06_machine_prefill_2026-10-09.json"
_SHA256 = re.compile(r"[0-9a-f]{64}\\Z")


def _unique(items: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        key = item[field]
        if not isinstance(key, str) or not key or key in result:
            raise ValueError(f"Missing or duplicate {field}: {key!r}")
        result[key] = item
    return result


def build_review(
    manifest: dict[str, Any],
    prior: dict[str, Any],
    prefill: dict[str, Any],
    *,
    as_of: datetime,
) -> dict[str, Any]:
    """Summarize archived evidence without implying current official availability."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must include a UTC offset")
    if manifest.get("schema_version") != "apr06-corpus-v1":
        raise ValueError("Unexpected candidate manifest schema")
    if (prior.get("schema_version") != "apr06-independent-gpt6-audit-v1"
            or prior.get("reviewer_type") != "separate_gpt6_model_assessment_over_rdc"
            or prior.get("human_operator_review") is not False
            or prior.get("human_signed_decisions") != 0
            or prior.get("final_commercial_acceptance") is not False):
        raise ValueError("Prior evidence cannot be treated as independent human truth")
    if prefill.get("schema_version") != "apr06-machine-prefill-v1":
        raise ValueError("Unexpected machine prefill schema")

    candidates = _unique(manifest["cases"], "reg_number")
    audited = _unique(prior["cases"], "reg_number")
    reports = _unique(prefill["cases"], "notice")
    if not set(audited) <= set(candidates) or not set(reports) <= set(candidates):
        raise ValueError("Source data includes procurement outside current manifest")
    if set(audited) != set(reports):
        raise ValueError("Independent archival review and machine report sets differ")

    findings = []
    archived_expired = 0
    archived_future = 0
    incomplete_extraction = 0
    for number, candidate in candidates.items():
        if candidate.get("verification", {}).get("state") != "candidate":
            raise ValueError("Unexpected verified/frozen source promotion")
        entry: dict[str, Any] = {
            "reg_number": number,
            "law": candidate["law"],
            "subject_candidate_only": candidate["subject"],
            "as_of": as_of.isoformat(),
            "current_eis_revision_verified": False,
            "current_eis_status_verified": False,
            "company_eligibility_verified": False,
            "human_reviewed": False,
            "bid_or_payment_authorized": False,
            "commercial_go": False,
            "model_review_not_human_truth": True,
            "listing_hint_not_original_eis": candidate["listing_source_url"],
        }
        old = audited.get(number)
        if old is None:
            entry.update({
                "evidence_tier": "AGGREGATOR_CANDIDATE_NO_ORIGINALS_IN_THIS_AUDIT",
                "advisory": "DEFER_INSUFFICIENT_PRIMARY_EIS_EVIDENCE",
                "archive_deadline_status": "NOT_MEASURED",
                "independent_document_review": "NOT_PERFORMED",
                "reasons": [
                    "No earlier source-read AI audit for this case",
                    "Original notice/attachment bytes and active revision have not been revalidated",
                ],
            })
        else:
            if (old.get("human_confirmed") is not False
                    or old.get("model_review_only") is not True
                    or old.get("external_action_allowed") is not False):
                raise ValueError("Prior model case has invalid human/action separation")
            notice = old["latest_archived_notice"]
            if not _SHA256.fullmatch(notice["source_sha256"]):
                raise ValueError("Invalid archived notice digest syntax")
            deadline = datetime.fromisoformat(notice["source_deadline"])
            if deadline.utcoffset() is None:
                raise ValueError("Archived deadline is timezone-naive")
            expired = deadline <= as_of
            if expired:
                archived_expired += 1
            else:
                archived_future += 1
            machine = reports[number]
            if machine.get("human_reviewed") is not False or machine.get("run_id") != old.get("run_id"):
                raise ValueError("Machine prefill cannot assert independent human review")
            total, readable = old["source_files_total"], old["source_text_flagged_available"]
            if readable < total:
                incomplete_extraction += 1
            entry.update({
                "evidence_tier": "PREVIOUSLY_SOURCE_READ_AI_AUDIT_NOT_REVALIDATED_TODAY",
                "archived_notice": {
                    "revision": notice["version"],
                    "deadline": notice["source_deadline"],
                    "sha256_recorded_by_previous_audit_not_rehashed": notice["source_sha256"],
                },
                "archive_deadline_status": (
                    "ARCHIVED_DEADLINE_PASSED" if expired else "ARCHIVED_DEADLINE_IN_FUTURE"
                ),
                "advisory": (
                    "NO_ACTION_ON_EXPIRED_ARCHIVED_DEADLINE_RECHECK_LIVE_EIS"
                    if expired else "DEFER_RECHECK_LIVE_EIS_AND_SPECIFICATIONS"
                ),
                "previous_machine_decision": machine["machine_decision"],
                "previous_ai_decision_at_original_audit_date": old["model_independent_recommendation"],
                "previous_audit_comparison": old["comparison"],
                "previous_audit_source_scope": old["model_source_read_scope"],
                "archived_source_files": total,
                "previously_text_available_files": readable,
                "independent_document_review": "PREVIOUS_MODEL_PARTIAL_REVIEW_ONLY",
                "previously_identified_conditions": old["key_conditions_and_unknowns"],
                "reasons": [
                    "Archived notice and limited document findings sourced from 2026-10-09 AI audit",
                    "Original EIS bytes and attachment-revision binding not rechecked in this run",
                ],
            })
        findings.append(entry)

    return {
        "schema_version": "apr06-ai-provisional-asof-v1",
        "as_of": as_of.isoformat(),
        "provenance": {
            "candidate_manifest": CANDIDATES.name,
            "prior_ai_audit": PRIOR_AUDIT.name,
            "machine_prefill": PREFILL.name,
            "new_eis_downloads": 0,
            "new_primary_bytes_verified": 0,
            "source_hashes_recomputed": 0,
        },
        "authority": {
            "reviewer_type": "AI_RETROSPECTIVE_PROVISIONAL",
            "human_signed_decisions": 0,
            "legal_acceptance": False,
            "commercial_acceptance": False,
            "owner_thresholds_approved": False,
            "bid_submissions_authorized": False,
        },
        "summary": {
            "candidate_ids": len(candidates),
            "prior_source_read_ai_cases": len(audited),
            "no_prior_primary_source_review": len(candidates) - len(audited),
            "archived_deadlines_passed_as_of_date": archived_expired,
            "archived_deadlines_future_as_of_date": archived_future,
            "prior_partial_text_extraction_cases": incomplete_extraction,
            "live_eis_verified_cases_today": 0,
            "actual_human_gold_cases": 0,
            "kpi_acceptance": "NOT_MEASURED",
        },
        "previously_known_defects_not_newly_verified": prior.get("critical_mismatches", []),
        "cases": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True, help="Offset-aware ISO-8601 timestamp")
    parser.add_argument("--output", required=True, type=Path, help="New file only; never overwrite")
    args = parser.parse_args()
    evidence = build_review(
        json.loads(CANDIDATES.read_text(encoding="utf-8")),
        json.loads(PRIOR_AUDIT.read_text(encoding="utf-8")),
        json.loads(PREFILL.read_text(encoding="utf-8")),
        as_of=datetime.fromisoformat(args.as_of),
    )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
        stream.write("\\n")
    print(json.dumps(evidence["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
