"""Read-only provenance coverage audit of the EXISTING Arvectum Procurement LLM corpus.

No writes, no data exports, no external network. Default stdout aggregates only;
identifying evidence/tenant fields must not be included in audit stdout.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path

from sqlalchemy import create_engine, func, select

from scripts.procurement_llm.import_candidates import _engine_url
from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.tender_research.models import TenderAnalysisRun

_REGISTRY = re.compile(r"\d{19}\Z")
_PROTECTED_SPLITS = {"blind", "blind_holdout", "independent_gold", "test_holdout"}
_PRIVATE_KEYS = {"raw_chat", "full_chat_transcript", "private_attachments", "api_key", "access_token"}


def _sha_file(path: Path, cache: dict[str, str | None]) -> str | None:
    """Hash original bytes without copying source material or exposing it."""
    key = str(path)
    if key not in cache:
        if not path.is_file() or path.is_symlink():
            cache[key] = None
        else:
            h = sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    h.update(chunk)
            cache[key] = h.hexdigest()
    return cache[key]


def audit_observations(
    observations: list[dict],
    known_run_ids: set[str],
    *,
    eis_root: Path,
    data_root: Path | None = None,
    preview_run_ids: set[str] | None = None,
) -> dict:
    """Pure classification except for read-only on-disk existence/SHA checks."""
    if data_root is None:
        data_root = eis_root.parents[2]
    preview_run_ids = preview_run_ids or set()
    count = Counter()
    manifest_cache: dict[str, str | None] = {}
    kinds = Counter()
    participations = Counter()
    manual_reviews = Counter()
    unique_refs = set()
    observation_ids = set()
    for row in observations:
        kind = row["event_kind"]
        kinds[kind] += 1
        ref = str(row["procurement_ref"])
        unique_refs.add(ref)
        oid = row["observation_id"]
        if oid in observation_ids:
            count["duplicate_observation_id"] += 1
        observation_ids.add(oid)
        payload = row["payload_json"]
        if not isinstance(payload, dict):
            count["invalid_payload"] += 1
            continue
        if row["training_status"] != "candidate_unreviewed":
            count["unexpected_training_status"] += 1
            if row["training_status"] == "train_ready":
                count["train_ready_observations"] += 1
        if payload.get("signed_human_gold") or payload.get("legal_gold") or payload.get("model_gold"):
            count["unapproved_gold_claim_present"] += 1
        source = payload.get("source")
        nested_role = source.get("source_role", "") if isinstance(source, dict) else ""
        if (
            row["candidate_split"].lower() in _PROTECTED_SPLITS
            or payload.get("protected_blind")
            or nested_role in {"blind", "blind_holdout", "r4_blind_holdout", "independent_gold"}
            or payload.get("source_role") in {"blind", "blind_holdout", "independent_gold"}
            or (isinstance(payload.get("tags", []), list) and "blind_holdout" in payload.get("tags", []))
        ):
            count["protected_split_present"] += 1
        if any(payload.get(k) for k in _PRIVATE_KEYS):
            count["sensitive_metadata_present"] += 1
        if _REGISTRY.fullmatch(ref):
            src_dir = eis_root / ref
            if src_dir.is_dir() and any(f.is_file() and not f.is_symlink() for f in src_dir.rglob("*")):
                count["existing_eis_originals"] += 1
            else:
                count["no_eis_originals_locally"] += 1
        else:
            count["non_eis_ref"] += 1
        if kind == "analysis_run":
            run_id = payload.get("run_id")
            if run_id and run_id in known_run_ids:
                count["linked_saved_analysis_runs"] += 1
            else:
                count["missing_saved_analysis_run"] += 1
            report = payload.get("report_path")
            if report:
                saved = Path(report)
                if saved.is_absolute() and saved.is_file() and not saved.is_symlink():
                    count["saved_report_path_readable_absolute"] += 1
                elif (
                    not saved.is_absolute()
                    and saved.parts[:3] == ("data", "rag", "reports")
                    and ".." not in saved.parts
                    and (data_root / saved).is_file()
                    and not (data_root / saved).is_symlink()
                ):
                    count["saved_report_path_resolved_canonical_relative"] += 1
                else:
                    count["saved_report_path_missing"] += 1
                    if run_id in preview_run_ids:
                        count["missing_report_has_db_preview_only"] += 1
            else:
                count["analysis_no_report_path"] += 1
        elif kind == "development_e2e":
            # Source SHA confirms the manifest, not the correctness of labels
            # and not the actual archived ZIP whose digest is claimed.
            for prefix in ("source_manifest", "metrics_manifest"):
                path = payload.get(f"{prefix}_path")
                expected = payload.get(f"{prefix}_sha256")
                if not path or not expected or not re.fullmatch(r"[0-9a-f]{64}", str(expected)):
                    count[f"{prefix}_unlinked"] += 1
                elif _sha_file(Path(path), manifest_cache) == expected:
                    count[f"{prefix}_sha_verified"] += 1
                else:
                    count[f"{prefix}_missing_or_sha_mismatch"] += 1
            source = payload.get("source") or {}
            if isinstance(source, dict) and re.fullmatch(r"[0-9a-f]{64}", str(source.get("archived_zip_sha256", ""))):
                count["dev_archive_sha_recorded_not_file_verified"] += 1
            else:
                count["dev_archive_sha_missing"] += 1
        elif kind == "manual_review":
            state = row["review_state"]
            manual_reviews[state] += 1
            participation = row["participation"]
            participations[participation] += 1
            if participation == "submitted" and not payload.get("participation_evidence"):
                count["manual_submitted_missing_evidence_basis"] += 1
            receipt = payload.get("primary_artifact")
            if isinstance(receipt, dict) and receipt.get("local_path") and receipt.get("sha256"):
                actual = _sha_file(Path(receipt["local_path"]), manifest_cache)
                if actual == receipt["sha256"]:
                    count["manual_original_sha_verified"] += 1
                else:
                    count["manual_original_missing_or_sha_mismatch"] += 1
            else:
                count["manual_no_sha_bound_receipt"] += 1
        else:
            count["unknown_kind"] += 1

    return {
        "total_observations": len(observations),
        "unique_observations": len(observation_ids),
        "unique_procurement_references": len(unique_refs),
        "kinds": dict(sorted(kinds.items())),
        "manual_participation": dict(sorted(participations.items())),
        "manual_review_confidence": dict(sorted(manual_reviews.items())),
        "checks": dict(sorted(count.items())),
        "train_ready": count["train_ready_observations"],
        "gold_claims_present": count["unapproved_gold_claim_present"],
        "scope": "metadata_integrity_only_no_gold_or_compliance_approval",
        "mutations": 0,
        "raw_source_files_copied": 0,
    }


def audit_live_database(eis_root: Path, data_root: Path | None = None) -> dict:
    # Connect only to existing arvectum, no shared Session or application-side
    # writes. PostgreSQL enforces read-only for the transaction.
    engine = create_engine(_engine_url(), future=True)
    try:
        if engine.dialect.name != "postgresql":
            raise ValueError("Live audit requires existing PostgreSQL 'arvectum'")
        with engine.connect() as conn, conn.begin():
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            rows = conn.execute(
                select(
                    ProcurementLearningObservation.observation_id,
                    ProcurementLearningObservation.event_kind,
                    ProcurementLearningObservation.procurement_ref,
                    ProcurementLearningObservation.review_state,
                    ProcurementLearningObservation.participation,
                    ProcurementLearningObservation.training_status,
                    ProcurementLearningObservation.candidate_split,
                    ProcurementLearningObservation.payload_json,
                )
            ).mappings().all()
            run_rows = conn.execute(
                select(TenderAnalysisRun.id, func.length(TenderAnalysisRun.report_markdown_preview))
            ).all()
            run_ids = {run_id for run_id, _length in run_rows}
            preview_run_ids = {run_id for run_id, length in run_rows if length and length > 0}
        return audit_observations(
            [dict(row) for row in rows], run_ids, eis_root=eis_root,
            data_root=data_root, preview_run_ids=preview_run_ids,
        )
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--eis-root", type=Path,
        default=Path("/Volumes/ArvectumSSD/Arvectum/data/tenders/eis"),
    )
    parser.add_argument("--expect-total", type=int, help="Fail if expected corpus volume changes")
    parser.add_argument("--data-root", type=Path, default=Path("/Volumes/ArvectumSSD/Arvectum"))
    args = parser.parse_args(argv)
    summary = audit_live_database(args.eis_root, args.data_root)
    print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    fail = (
        (args.expect_total is not None and summary["total_observations"] != args.expect_total)
        or summary["checks"].get("duplicate_observation_id", 0) > 0
        or summary["checks"].get("protected_split_present", 0) > 0
        or summary["checks"].get("sensitive_metadata_present", 0) > 0
        or summary["checks"].get("unexpected_training_status", 0) > 0
        or summary["checks"].get("unapproved_gold_claim_present", 0) > 0
    )
    return 2 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
