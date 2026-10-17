"""APR-07 independent procurement benchmark *candidate* roster; never gold labels."""
from __future__ import annotations

import json
from pathlib import Path

from src.modules.benchmark_pipeline.contract import canonical_sha256
from src.modules.quality_slo.snapshot import QualityEvidenceError, load, unique


def build_candidate_roster(repo_root: Path) -> dict:
    base = repo_root / "docs" / "acceptance"
    receipts, receipt_sha = load(base / "apr06_real_probe_receipts_2026-10-09.json")
    audit, audit_sha = load(base / "apr06_independent_gpt6_audit_2026-10-09.json")
    originals = unique(receipts.get("cases"), "reg_number")
    candidates = unique(audit.get("cases"), "reg_number")
    if audit.get("human_operator_review") is not False or audit.get("human_signed_decisions") != 0:
        raise QualityEvidenceError("human gold cannot come from AI audit")
    cases = []
    for reg, review in sorted(candidates.items()):
        source = originals.get(reg)
        if not source or review.get("run_id") != source.get("run_id"):
            raise QualityEvidenceError(f"unbound source run: {reg}")
        documents = source.get("document_files")
        if not isinstance(documents, list) or not documents:
            raise QualityEvidenceError(f"missing actual EIS documents: {reg}")
        files = {item["file_id"]: item for item in documents}
        if len(files) != len(documents):
            raise QualityEvidenceError(f"duplicate files in case: {reg}")
        latest = review.get("latest_archived_notice")
        if not isinstance(latest, dict) or latest.get("version", 0) < 1:
            raise QualityEvidenceError(f"invalid latest notice revision: {reg}")
        notice_id = latest.get("file_id")
        if notice_id not in files or files[notice_id]["sha256"] != latest.get("source_sha256"):
            raise QualityEvidenceError(f"notice hash not bound to source files: {reg}")
        for attachment in review.get("spec_and_contract_source_hashes", []):
            if (attachment.get("file_id") not in files
                    or files[attachment["file_id"]]["sha256"] != attachment.get("sha256")):
                raise QualityEvidenceError(f"attachment mismatch: {reg}")
        # Do not export AI GO/NO_GO as gold or reveal text/personal documents.
        case = {
            "reg_number": reg, "law": "44fz", "run_id": source["run_id"],
            "latest_archived_notice_version": latest["version"],
            "notice_file_id": notice_id, "notice_sha256": latest["source_sha256"],
            "available_file_count": len(documents),
            "source_bundle_sha256": canonical_sha256(sorted(
                ({"file_id": item["file_id"], "sha256": item["sha256"]}
                 for item in documents), key=lambda i: i["file_id"])),
            "label_state": "AI_CURATED_SILVER_NOT_HUMAN_GOLD",
            "human_review_completed": False,
            "attachment_revision_binding_verified": False,
            "verified_answer_labels": None,
        }
        cases.append(case)
    bundle = {
        "schema_version": "apr07-procurement-roster-v1",
        "purpose": "source_provenance_only_not_blind_evaluator_labels",
        "number_of_candidates": len(cases),
        "all_cases_are_human_gold": False,
        "candidate_sources_sha256": {"receipts": receipt_sha, "ai_review": audit_sha},
        "cases": cases,
    }
    bundle["roster_sha256"] = canonical_sha256(bundle)
    return bundle


def save_exclusive(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
