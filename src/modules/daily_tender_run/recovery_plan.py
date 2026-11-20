"""Read-only exact-scope recovery inventory for the daily operator.

Never calls discovery, analysis, intake, post-decision actions or ingestion.
A candidate is an observation, not authorization or a live-write receipt.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.daily_tender_run.models import DailyTenderRun, DailyTenderRunItem
from src.modules.deal_registry.models import Deal
from src.tender_research.models import ProcurementTender, TenderAnalysisRun
from src.tender_research.rag.data_platform import build_tender_collection_id
from src.tender_research.repository import TenderRepository


@dataclass(frozen=True)
class RecoveryTarget:
    run_id: str
    registry_number: str
    expected_deal_id: str
    expected_source_fingerprint: str

    def __post_init__(self):
        if not re.fullmatch(r"[0-9a-f]{64}", self.expected_source_fingerprint):
            raise ValueError("exact full source fingerprint required")
        if not re.fullmatch(r"[0-9]{19}", self.registry_number):
            raise ValueError("only exact 44-FZ registry identity supported")
        if not self.run_id or not self.expected_deal_id:
            raise ValueError("missing existing run/deal identity")


def plan_target(session: Session, target: RecoveryTarget) -> dict:
    q = (
        select(DailyTenderRunItem, DailyTenderRun)
        .join(DailyTenderRun, DailyTenderRunItem.run_id == DailyTenderRun.run_id)
        .where(DailyTenderRunItem.registry_number == target.registry_number)
    )
    siblings = session.execute(q).all()
    matches = [(i, r) for i, r in siblings if r.run_id == target.run_id]
    result = {"target": asdict(target)}

    def decision(status, **fields):
        return {**result, "status": status, **fields}

    if len(matches) != 1:
        return decision("identity_mismatch")
    item, run = matches[0]
    if (
        item.deal_id != target.expected_deal_id
        or item.source_fingerprint != target.expected_source_fingerprint
        or item.law != "44fz"
        or item.source != "public_eis_html_44fz"
    ):
        return decision("identity_mismatch")
    same = [
        i
        for i, r in siblings
        if i.deal_id == item.deal_id and i.source_fingerprint == item.source_fingerprint
    ]
    if any(
        i.status == "MANAGER_READY"
        and i.analysis_run_id
        and str(i.analysis_status or "").startswith("completed")
        for i in same
    ):
        return decision("already_completed")
    if any(
        i.human_decision
        or i.human_decision_id
        or i.post_decision_json
        or i.status == "PROCESSING"
        or r.status == "RUNNING"
        for i, r in siblings
    ):
        return decision("human_or_active_work_review")
    if any(
        i.source_fingerprint != item.source_fingerprint or i.deal_id != item.deal_id
        for i, r in siblings
    ):
        return decision("other_revision_or_deal_review")
    if (
        item.status != "FAILED"
        or item.analysis_run_id
        or item.analysis_status
        or item.analysis_report_path
        or item.synthesis_json
    ):
        return decision("prior_analysis_or_status_review")
    histories = session.scalars(
        select(TenderAnalysisRun).where(
            TenderAnalysisRun.registry_number == target.registry_number
        )
    ).all()
    if histories:
        return decision("unreconciled_analysis_history", history_count=len(histories))
    deals = session.scalars(
        select(Deal).where(
            Deal.procurement_number == target.registry_number,
            Deal.is_deleted.is_(False),
        )
    ).all()
    if len(deals) != 1 or deals[0].deal_id != item.deal_id or deals[0].archived_at:
        return decision("deal_identity_review")
    tenders = session.scalars(
        select(ProcurementTender).where(
            ProcurementTender.registry_number == target.registry_number
        )
    ).all()
    if len(tenders) != 1 or tenders[0].source != "eis" or tenders[0].law_type != "44fz":
        return decision("tender_identity_review")
    tender = tenders[0]
    repo = TenderRepository(session)
    chunks = repo.list_chunks_by_tender(tender.id)
    return decision(
        "candidate_for_reviewed_recovery",
        tender_id=str(tender.id),
        documents=len(tender.documents),
        chunks=len(chunks),
        collection_id=build_tender_collection_id(repo, tender.id),
        profile_id=run.profile_id,
        missing_documents=sum(
            d.download_status != "downloaded" for d in tender.documents
        ),
    )
