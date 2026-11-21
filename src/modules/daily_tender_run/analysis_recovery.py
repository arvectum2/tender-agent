"""Exact existing-item completion, after independent index verification.

No discovery, ingestion, new deals, external actions or notifications.
Callers own admission, the daily execution guard, and the durable attempt
journal. History plus manager-ready item and digest commit atomically.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.daily_tender_run.manager_synthesis import ManagerSynthesis
from src.modules.daily_tender_run.models import DailyTenderRun, DailyTenderRunItem
from src.modules.daily_tender_run.recovery_plan import RecoveryTarget, plan_target
from src.modules.daily_tender_run.schemas import DailyTenderProfile
from src.modules.daily_tender_run.service import _counts, _digest
from src.shared.db.base import utcnow
from src.tender_research.rag.analysis_service import _build_history_metadata
from src.tender_research.rag.history_service import record_analysis_run
from src.tender_research.rag.schemas import TenderAnalysisResult


def profile_for_target(session: Session, target: RecoveryTarget):
    run = session.scalars(
        select(DailyTenderRun).where(DailyTenderRun.run_id == target.run_id)
    ).one()
    profile = DailyTenderProfile.model_validate(run.profile_snapshot_json)
    if (profile.profile_id, profile.version, profile.law) != (
        run.profile_id,
        run.profile_version,
        "44fz",
    ):
        raise ValueError("stored profile identity mismatch")
    return profile


def complete_indexed_analysis(
    session: Session,
    *,
    target: RecoveryTarget,
    analysis: TenderAnalysisResult,
    synthesis: ManagerSynthesis,
    report: Path,
    expected_profile: DailyTenderProfile,
    index_identity_sha256: str,
    report_sha256: str,
) -> dict:
    """Stage one transaction, never commits on behalf of the operator."""
    # Lock the run first, consistent with the service's run-level guard.
    run = session.scalars(
        select(DailyTenderRun)
        .where(DailyTenderRun.run_id == target.run_id)
        .with_for_update()
    ).one()
    item = session.scalars(
        select(DailyTenderRunItem)
        .where(
            DailyTenderRunItem.run_id == target.run_id,
            DailyTenderRunItem.registry_number == target.registry_number,
        )
        .with_for_update()
    ).one()
    session.refresh(run)
    session.refresh(item)
    if run.status not in {"WAITING_HUMAN", "COMPLETED_WITH_ERRORS"}:
        raise ValueError("unsupported original daily run status")
    plan = plan_target(session, target)
    if plan["status"] != "candidate_for_reviewed_recovery":
        raise ValueError("target is not an exact pending recovery candidate")
    if profile_for_target(session, target) != expected_profile:
        raise ValueError("daily profile changed")
    if (
        analysis.registry_number != target.registry_number
        or analysis.status not in {"completed", "completed_with_warnings"}
        or analysis.run_id is not None
        or analysis.analysis_mode != expected_profile.analysis_mode
        or (expected_profile.analysis_use_llm and not analysis.used_llm)
        or analysis.errors
        or not analysis.report_markdown.strip()
        or not analysis.sections
        or analysis.sections_count != len(analysis.sections)
        or analysis.sources_count <= 0
        or not synthesis.human_control_required
    ):
        raise ValueError("analysis or human-control evidence incomplete")
    for value in (index_identity_sha256, report_sha256):
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("invalid recovery evidence hash")
    if not report.is_absolute() or report.is_symlink() or not report.is_file():
        raise ValueError("missing report artifact")
    content = analysis.report_markdown.encode("utf-8")
    if (
        hashlib.sha256(content).hexdigest() != report_sha256
        or report.read_bytes() != content
    ):
        raise ValueError("saved report differs from completed analysis")
    original_error = item.error
    metadata = _build_history_metadata(analysis)
    metadata["daily_recovery"] = {
        "run_id": run.run_id,
        "item_id": item.id,
        "deal_id": item.deal_id,
        "source_fingerprint": item.source_fingerprint,
        "prior_status": item.status,
        "prior_stage": item.stage,
        "prior_error": original_error,
        "index_identity_sha256": index_identity_sha256,
        "report_sha256": report_sha256,
    }
    history = record_analysis_run(
        session,
        registry_number=target.registry_number,
        status=analysis.status,
        used_llm=analysis.used_llm,
        llm_model=analysis.llm_model,
        retrieval_provider=analysis.retrieval_provider,
        retrieval_model=analysis.retrieval_model,
        sections_count=analysis.sections_count,
        sources_count=analysis.sources_count,
        report_path=str(report),
        report_markdown=analysis.report_markdown,
        warnings=analysis.warnings,
        errors=analysis.errors,
        duration_seconds=analysis.duration_seconds,
        source="daily_tender_recovery",
        metadata=metadata,
        commit=False,
    )
    item.analysis_run_id = history.id
    item.analysis_status = analysis.status
    item.analysis_report_path = str(report)
    item.agent_recommendation = synthesis.recommendation
    item.agent_confidence = synthesis.confidence
    item.agent_rationale = synthesis.rationale
    item.strongest_reasons_json = list(synthesis.strongest_reasons)
    item.blockers_json = list(synthesis.blockers)
    item.unknowns_json = list(synthesis.unknowns)
    item.synthesis_json = synthesis.model_dump(mode="json")
    item.stage = "WAIT_HUMAN"
    item.status = "MANAGER_READY"
    item.error = None
    item.updated_at = utcnow()
    session.flush()
    items = list(
        session.scalars(
            select(DailyTenderRunItem).where(DailyTenderRunItem.run_id == run.run_id)
        )
    )
    run.counts_json = _counts(items)
    run.counts_json = {
        **run.counts_json,
        "discovery_incomplete": int(bool(run.error_summary)),
    }
    run.digest_json = _digest(run, items)
    run.current_stage = "WAIT_HUMAN"
    run.status = "WAITING_HUMAN"
    run.updated_at = utcnow()
    session.flush()
    return {
        "run_id": run.run_id,
        "registry_number": target.registry_number,
        "deal_id": item.deal_id,
        "analysis_run_id": history.id,
        "status": item.status,
        "report_sha256": report_sha256,
    }
