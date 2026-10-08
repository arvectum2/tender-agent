from fastapi import APIRouter, status

from src.modules.case_collaboration.schemas import (
    AppendCaseJournalEntryRequest,
    CaseJournalEntryResponse,
    CaseJournalEvidenceResponse,
    CaseJournalMentionResponse,
)
from src.modules.case_collaboration.service import (
    append_case_journal_entry,
    entry_evidence,
    entry_mentions,
    get_case_journal_entry,
    list_case_journal_entries,
)
from src.shared.api.dependencies import DBSession

router = APIRouter(
    prefix="/api/operator/pilot/customers/{customer_id}/cases/{case_id}/discussion",
    tags=["case-collaboration"],
)


def _response(session: DBSession, entry) -> CaseJournalEntryResponse:
    return CaseJournalEntryResponse(
        id=entry.id,
        customer_id=entry.customer_id,
        project_id=entry.project_id,
        procurement_case_id=entry.procurement_case_id,
        entry_type=entry.entry_type,
        actor_type=entry.actor_type,
        actor_ref=entry.actor_ref,
        body=entry.body,
        decision_code=entry.decision_code,
        supersedes_entry_id=entry.supersedes_entry_id,
        created_at=entry.created_at,
        mentions=[
            CaseJournalMentionResponse.model_validate(item)
            for item in entry_mentions(session, entry.id)
        ],
        evidence_links=[
            CaseJournalEvidenceResponse.model_validate(item)
            for item in entry_evidence(session, entry.id)
        ],
    )


@router.post(
    "/entries",
    response_model=CaseJournalEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def append_entry(
    customer_id: str,
    case_id: str,
    payload: AppendCaseJournalEntryRequest,
    session: DBSession,
) -> CaseJournalEntryResponse:
    return _response(
        session,
        append_case_journal_entry(
            session,
            customer_id=customer_id,
            case_id=case_id,
            payload=payload,
        ),
    )


@router.get("/entries", response_model=list[CaseJournalEntryResponse])
def list_entries(
    customer_id: str,
    case_id: str,
    session: DBSession,
) -> list[CaseJournalEntryResponse]:
    return [
        _response(session, item)
        for item in list_case_journal_entries(
            session,
            customer_id=customer_id,
            case_id=case_id,
        )
    ]


@router.get("/entries/{entry_id}", response_model=CaseJournalEntryResponse)
def get_entry(
    customer_id: str,
    case_id: str,
    entry_id: str,
    session: DBSession,
) -> CaseJournalEntryResponse:
    return _response(
        session,
        get_case_journal_entry(
            session,
            customer_id=customer_id,
            case_id=case_id,
            entry_id=entry_id,
        ),
    )
