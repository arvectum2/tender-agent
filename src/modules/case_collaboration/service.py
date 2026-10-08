from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.case_collaboration.models import (
    CaseJournalEntry,
    CaseJournalEvidenceLink,
    CaseJournalMention,
)
from src.modules.case_collaboration.schemas import AppendCaseJournalEntryRequest
from src.modules.customer_pilot.models import (
    PilotArtifact,
    PilotAuditEvent,
    ProcurementCase,
)
from src.shared.errors import NotFoundError, ValidationError
from src.shared.validation import require_non_empty
from src.tender_research.models import TenderAnalysisRun

_MENTION_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9_.:-]{1,255})")


def _scoped_case(
    session: Session,
    *,
    customer_id: str,
    case_id: str,
) -> ProcurementCase:
    case = session.scalar(
        select(ProcurementCase).where(
            ProcurementCase.id == case_id,
            ProcurementCase.customer_id == customer_id,
        )
    )
    if not case:
        raise NotFoundError("Procurement case not found")
    return case


def _entry_in_scope(
    session: Session,
    *,
    customer_id: str,
    case_id: str,
    entry_id: str,
) -> CaseJournalEntry:
    entry = session.scalar(
        select(CaseJournalEntry).where(
            CaseJournalEntry.id == entry_id,
            CaseJournalEntry.customer_id == customer_id,
            CaseJournalEntry.procurement_case_id == case_id,
        )
    )
    if not entry:
        raise NotFoundError("Case journal entry not found")
    return entry


def _normalized_mentions(body: str, explicit: list[str]) -> list[str]:
    values = {
        token.strip().lstrip("@")
        for token in [*explicit, *_MENTION_RE.findall(body)]
        if token and token.strip().lstrip("@")
    }
    return sorted(values)


def _validate_evidence_ref(
    session: Session,
    *,
    case: ProcurementCase,
    source_type: str,
    source_ref: str,
) -> None:
    source_type = source_type.upper()
    if source_type == "PROCUREMENT_CASE":
        if source_ref != case.id:
            raise ValidationError(
                "PROCUREMENT_CASE evidence must reference the current case"
            )
        return
    if source_type == "PILOT_ARTIFACT":
        found = session.scalar(
            select(PilotArtifact.id).where(
                PilotArtifact.id == source_ref,
                PilotArtifact.customer_id == case.customer_id,
                PilotArtifact.procurement_case_id == case.id,
            )
        )
        if not found:
            raise ValidationError(
                "PILOT_ARTIFACT evidence is not in the current tenant/case"
            )
        return
    if source_type == "ANALYSIS_RUN":
        found = session.scalar(
            select(TenderAnalysisRun.id).where(
                TenderAnalysisRun.id == source_ref,
                TenderAnalysisRun.customer_id == case.customer_id,
                TenderAnalysisRun.procurement_case_id == case.id,
            )
        )
        if not found:
            raise ValidationError(
                "ANALYSIS_RUN evidence is not in the current tenant/case"
            )


def append_case_journal_entry(
    session: Session,
    *,
    customer_id: str,
    case_id: str,
    payload: AppendCaseJournalEntryRequest,
) -> CaseJournalEntry:
    case = _scoped_case(session, customer_id=customer_id, case_id=case_id)
    actor_type = require_non_empty(payload.actor_type, "actor_type")
    actor_ref = require_non_empty(payload.actor_ref, "actor_ref")
    body = require_non_empty(payload.body, "body")

    if payload.supersedes_entry_id:
        previous = _entry_in_scope(
            session,
            customer_id=customer_id,
            case_id=case_id,
            entry_id=payload.supersedes_entry_id,
        )
        if payload.entry_type != "DECISION" or previous.entry_type != "DECISION":
            raise ValidationError("Only a DECISION may supersede another DECISION")

    for link in payload.evidence_links:
        _validate_evidence_ref(
            session,
            case=case,
            source_type=link.source_type,
            source_ref=link.source_ref,
        )

    entry = CaseJournalEntry(
        customer_id=case.customer_id,
        project_id=case.project_id,
        procurement_case_id=case.id,
        entry_type=payload.entry_type,
        actor_type=actor_type,
        actor_ref=actor_ref,
        body=body,
        decision_code=payload.decision_code,
        supersedes_entry_id=payload.supersedes_entry_id,
    )
    session.add(entry)
    session.flush()

    mentions = _normalized_mentions(body, payload.mention_refs)
    for mention_ref in mentions:
        session.add(
            CaseJournalMention(
                journal_entry_id=entry.id,
                mention_ref=mention_ref,
                notification_state="INTERNAL_UNREAD",
            )
        )

    for link in payload.evidence_links:
        session.add(
            CaseJournalEvidenceLink(
                journal_entry_id=entry.id,
                source_type=link.source_type.upper(),
                source_ref=link.source_ref,
            )
        )

    session.add(
        PilotAuditEvent(
            customer_id=case.customer_id,
            project_id=case.project_id,
            procurement_case_id=case.id,
            event_type="case_journal_entry_recorded",
            payload={
                "entry_id": entry.id,
                "entry_type": entry.entry_type,
                "actor_type": entry.actor_type,
                "actor_ref": entry.actor_ref,
                "decision_code": entry.decision_code,
                "mention_count": len(mentions),
                "evidence_link_count": len(payload.evidence_links),
                "notification_channel": "internal_only",
            },
        )
    )
    session.commit()
    session.refresh(entry)
    return entry


def list_case_journal_entries(
    session: Session,
    *,
    customer_id: str,
    case_id: str,
) -> list[CaseJournalEntry]:
    _scoped_case(session, customer_id=customer_id, case_id=case_id)
    return list(
        session.scalars(
            select(CaseJournalEntry)
            .where(
                CaseJournalEntry.customer_id == customer_id,
                CaseJournalEntry.procurement_case_id == case_id,
            )
            .order_by(CaseJournalEntry.created_at.asc(), CaseJournalEntry.id.asc())
        )
    )


def get_case_journal_entry(
    session: Session,
    *,
    customer_id: str,
    case_id: str,
    entry_id: str,
) -> CaseJournalEntry:
    _scoped_case(session, customer_id=customer_id, case_id=case_id)
    return _entry_in_scope(
        session,
        customer_id=customer_id,
        case_id=case_id,
        entry_id=entry_id,
    )


def entry_mentions(session: Session, entry_id: str) -> list[CaseJournalMention]:
    return list(
        session.scalars(
            select(CaseJournalMention)
            .where(CaseJournalMention.journal_entry_id == entry_id)
            .order_by(CaseJournalMention.created_at.asc(), CaseJournalMention.id.asc())
        )
    )


def entry_evidence(session: Session, entry_id: str) -> list[CaseJournalEvidenceLink]:
    return list(
        session.scalars(
            select(CaseJournalEvidenceLink)
            .where(CaseJournalEvidenceLink.journal_entry_id == entry_id)
            .order_by(
                CaseJournalEvidenceLink.created_at.asc(),
                CaseJournalEvidenceLink.id.asc(),
            )
        )
    )
