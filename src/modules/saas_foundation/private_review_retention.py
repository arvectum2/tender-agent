"""Internal planning only; no public API, writes, deletion or access authority."""
from datetime import date, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from sqlalchemy import select

from .models import PrivateReviewRetentionProposal

Reference = Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$')]


class ScheduleProposal(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    order_ref: Reference
    policy_ref: Reference
    order_ended_on: date | None = None
    end_evidence_ref: Reference | None = None
    working_days: StrictInt = Field(ge=0, le=3650)
    backup_days: StrictInt = Field(ge=0, le=3650)
    hold_state: Literal['UNKNOWN', 'ACTIVE', 'CLEAR'] = 'UNKNOWN'
    hold_evidence_ref: Reference | None = None
    hold_review_on: date | None = None

    @model_validator(mode='after')
    def consistent(self):
        if (self.order_ended_on is None) != (self.end_evidence_ref is None):
            raise ValueError('Order-end date and evidence reference must be paired')
        if self.backup_days < self.working_days:
            raise ValueError('Backup horizon precedes working-copy horizon')
        if self.hold_state == 'UNKNOWN':
            if self.hold_evidence_ref or self.hold_review_on:
                raise ValueError('Unknown hold state cannot carry an attestation')
        elif not self.hold_evidence_ref or not self.hold_review_on:
            raise ValueError('Explicit hold state requires evidence and next review date')
        if self.order_ended_on:
            try:
                self.order_ended_on + timedelta(days=self.backup_days)
            except OverflowError as exc:
                raise ValueError('Proposed horizon exceeds supported calendar') from exc
        return self


def describe(proposal: ScheduleProposal, *, as_of: date) -> dict:
    """Calendar planning dates, not verified facts or permission to remove."""
    reasons = ['POLICY_APPROVAL_UNVERIFIED', 'DOCUMENT_ORDER_BINDING_UNVERIFIED']
    ended = proposal.order_ended_on
    working = backup = None
    if ended is None:
        reasons.append('ORDER_END_UNKNOWN')
    elif ended > as_of:
        reasons.append('ORDER_END_IN_FUTURE')
    else:
        working = (ended+timedelta(days=proposal.working_days)).isoformat()
        backup = (ended+timedelta(days=proposal.backup_days)).isoformat()
    if proposal.hold_state == 'UNKNOWN':
        reasons.append('HOLD_STATE_UNKNOWN')
    elif proposal.hold_state == 'ACTIVE':
        reasons.append('HOLD_ACTIVE')
    if proposal.hold_review_on is not None and proposal.hold_review_on <= as_of:
        reasons.append('HOLD_REVIEW_DUE')
    return {'status':'PROPOSED_NOT_APPROVED', 'as_of':as_of.isoformat(),
            'proposed_working_until':working, 'proposed_backup_until':backup,
            'blocking_reasons':reasons, 'deletion_authorized':False,
            'access_change_authorized':False}


def latest_proposal(session, *, tenant_id: str, order_ref: str):
    """Internal scoped lookup; caller must independently authorize access.
    Not mounted as an API and does not expose documents or mutate state.
    """
    return session.scalar(select(PrivateReviewRetentionProposal).where(
        PrivateReviewRetentionProposal.tenant_id == tenant_id,
        PrivateReviewRetentionProposal.order_ref == order_ref,
    ).order_by(PrivateReviewRetentionProposal.revision.desc()).limit(1))
