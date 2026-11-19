"""Internal planning only; no public API, writes, deletion or access authority."""
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from sqlalchemy import and_, func, select

from .models import (
    ApplicationReviewPreview,
    OriginalFormReviewCandidate,
    PrivateReviewOrderLink,
    PrivateReviewRetentionProposal,
)

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


def storage_summary(session, *, tenant_id: str, now: datetime) -> dict:
    """Scoped internal counts only. Caller independently authorizes tenant.

    Counts payload bytes, not physical database usage. No blob or JSON is
    fetched, no automatic association, no permission or mutation.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Timezone-aware observation required')
    if session.new or session.dirty or session.deleted:
        raise ValueError('Clean read-only session required')
    now = now.astimezone(UTC)
    stats = {}
    for kind, model, content, link_column in (
        ('archives', ApplicationReviewPreview, ApplicationReviewPreview.archive_bytes, PrivateReviewOrderLink.preview_id),
        ('forms', OriginalFormReviewCandidate, OriginalFormReviewCandidate.document_bytes, PrivateReviewOrderLink.candidate_id),
    ):
        link = PrivateReviewOrderLink
        q = select(model.expires_at, func.length(content), link.id, link.proposal_id).outerjoin(
            link, and_(link.tenant_id == model.tenant_id, link_column == model.id)
        ).where(model.tenant_id == tenant_id).limit(1001)
        rows = list(session.execute(q))
        if len(rows) > 1000:
            raise ValueError('Accounting scope exceeds bounded report')
        counts = dict.fromkeys(('count', 'payload_bytes', 'expired', 'unlinked', 'proposed_links',
                                'proposal_missing', 'proposal_superseded', 'hold_unknown',
                                'hold_active', 'hold_review_due', 'working_horizon_reached',
                                'backup_horizon_reached'), 0)
        for expiry, length, link_id, proposal_id in rows:
            counts['count'] += 1
            counts['payload_bytes'] += int(length)
            expiry = expiry.replace(tzinfo=UTC) if expiry.tzinfo is None else expiry.astimezone(UTC)
            counts['expired'] += int(expiry <= now)
            if link_id is None:
                counts['unlinked'] += 1
                continue
            counts['proposed_links'] += 1
            pinned = session.scalar(select(PrivateReviewRetentionProposal).where(
                PrivateReviewRetentionProposal.tenant_id == tenant_id,
                PrivateReviewRetentionProposal.id == proposal_id))
            if pinned is None:
                counts['proposal_missing'] += 1
                continue
            current = latest_proposal(session, tenant_id=tenant_id, order_ref=pinned.order_ref)
            if current is None or current.id != pinned.id:
                counts['proposal_superseded'] += 1
                continue
            try:
                proposal = ScheduleProposal.model_validate(
                    {name: getattr(pinned, name) for name in ScheduleProposal.model_fields})
            except ValueError:
                counts['proposal_missing'] += 1
                continue
            result = describe(proposal, as_of=now.date())
            reasons = result['blocking_reasons']
            counts['hold_unknown'] += int('HOLD_STATE_UNKNOWN' in reasons)
            counts['hold_active'] += int('HOLD_ACTIVE' in reasons)
            counts['hold_review_due'] += int('HOLD_REVIEW_DUE' in reasons)
            for field, metric in (('proposed_working_until', 'working_horizon_reached'),
                                  ('proposed_backup_until', 'backup_horizon_reached')):
                counts[metric] += int(result[field] is not None and result[field] <= now.date().isoformat())
        stats[kind] = counts
    return {'status': 'INTERNAL_PROPOSED_ACCOUNTING_ONLY', 'observed_at': now.isoformat(),
            **stats, 'physical_storage_measured': False, 'order_ownership_verified': False,
            'deletion_authorized': False, 'access_change_authorized': False}
