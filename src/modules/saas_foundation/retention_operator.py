"""Internal operator proposals; not an approval, access or deletion capability."""
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .models import (
    ApplicationReviewPreview,
    OriginalFormReviewCandidate,
    PrivateReviewLinkCorrection,
    PrivateReviewOrderLink,
    PrivateReviewRetentionProposal,
    SaasTenant,
)
from .private_review_retention import (
    Reference,
    ScheduleProposal,
    describe,
    latest_link_correction,
    latest_proposal,
    storage_summary,
)
from .service import audit, now_utc

Identifier = Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{1,128}$')]
MAX_PROPOSALS = 200


class AppendProposal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: StrictInt = Field(ge=0, le=MAX_PROPOSALS)
    schedule: ScheduleProposal
    confirm_proposal_only: StrictBool


class ProposeLink(BaseModel):
    model_config = ConfigDict(extra='forbid')
    proposal_id: Identifier
    document_kind: Literal['archive', 'form']
    document_id: Identifier
    evidence_ref: Reference
    confirm_proposal_only: StrictBool


class CorrectLink(BaseModel):
    model_config = ConfigDict(extra='forbid')
    link_id: Identifier
    expected_revision: StrictInt = Field(ge=0, le=200)
    proposal_id: Identifier
    evidence_ref: Reference
    confirm_proposal_only: StrictBool


def _tenant(session, tenant_id, *, lock=False):
    q = select(SaasTenant.tenant_id).where(SaasTenant.tenant_id == tenant_id)
    if lock:
        q = q.with_for_update()
    if session.scalar(q) is None:
        raise HTTPException(404, 'Tenant not found')


def _view(row):
    schedule = ScheduleProposal.model_validate(
        {name: getattr(row, name) for name in ScheduleProposal.model_fields})
    return {'proposal_id': row.id, 'revision': row.revision,
            'schedule': schedule.model_dump(mode='json'),
            'planning': describe(schedule, as_of=now_utc().date())}


def overview(session, tenant_id):
    _tenant(session, tenant_id)
    try:
        result = storage_summary(session, tenant_id=tenant_id, now=now_utc())
    except ValueError as exc:
        raise HTTPException(409, 'Accounting unavailable') from exc
    rows = list(session.scalars(select(PrivateReviewRetentionProposal).where(
        PrivateReviewRetentionProposal.tenant_id == tenant_id
    ).order_by(PrivateReviewRetentionProposal.order_ref, PrivateReviewRetentionProposal.revision.desc()).limit(MAX_PROPOSALS+1)))
    if len(rows) > MAX_PROPOSALS:
        raise HTTPException(409, 'Proposal history exceeds console limit')
    proposals = {}
    for row in rows:
        if row.order_ref not in proposals:
            try:
                proposals[row.order_ref] = _view(row)
            except ValueError as exc:
                raise HTTPException(409, 'Proposal record inconsistent') from exc
    documents = []
    for kind, model, col in (
        ('archive', ApplicationReviewPreview, PrivateReviewOrderLink.preview_id),
        ('form', OriginalFormReviewCandidate, PrivateReviewOrderLink.candidate_id),
    ):
        q = select(model.id, model.expires_at, PrivateReviewOrderLink.id, PrivateReviewOrderLink.proposal_id).outerjoin(
            PrivateReviewOrderLink, (model.tenant_id == PrivateReviewOrderLink.tenant_id) & (model.id == col)
        ).where(model.tenant_id == tenant_id).order_by(model.id).limit(21)
        found = list(session.execute(q))
        if len(found) > 20:
            raise HTTPException(409, 'Document inventory exceeds console limit')
        for identity, expiry, link_id, original in found:
            correction = latest_link_correction(session, tenant_id=tenant_id, link_id=link_id) if link_id else None
            documents.append({'kind': kind, 'id': identity, 'expires_at': expiry.isoformat(),
                'link_id': link_id, 'original_proposal': original,
                'proposed_link': correction.proposal_id if correction else original,
                'link_revision': correction.revision if correction else 0})
    return {'accounting': result, 'proposals': list(proposals.values()), 'documents': documents,
            'operator_identity_verified': False, 'deletion_authorized': False}


def append_proposal(session, tenant_id, payload):
    if not payload.confirm_proposal_only:
        raise HTTPException(409, 'Confirm proposal-only recording')
    _tenant(session, tenant_id, lock=True)
    old = latest_proposal(session, tenant_id=tenant_id, order_ref=payload.schedule.order_ref)
    revision = old.revision if old else 0
    if revision != payload.expected_revision:
        raise HTTPException(409, 'Proposal revision changed; refresh')
    count = session.scalar(select(func.count(PrivateReviewRetentionProposal.id)).where(
        PrivateReviewRetentionProposal.tenant_id == tenant_id))
    if count >= MAX_PROPOSALS:
        raise HTTPException(429, 'Proposal history limit reached')
    row = PrivateReviewRetentionProposal(tenant_id=tenant_id, revision=revision+1, **payload.schedule.model_dump())
    session.add(row)
    try:
        session.flush()
        audit(session, tenant_id, 'retention_proposal_recorded', detail=row.id)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, 'Concurrent proposal; refresh') from exc
    return _view(row)


def propose_link(session, tenant_id, payload):
    if not payload.confirm_proposal_only:
        raise HTTPException(409, 'Confirm proposal-only recording')
    _tenant(session, tenant_id, lock=True)
    row = session.scalar(select(PrivateReviewRetentionProposal).where(
        PrivateReviewRetentionProposal.tenant_id == tenant_id,
        PrivateReviewRetentionProposal.id == payload.proposal_id))
    if row is None:
        raise HTTPException(404, 'Proposal not found')
    current = latest_proposal(session, tenant_id=tenant_id, order_ref=row.order_ref)
    if current is None or current.id != row.id:
        raise HTTPException(409, 'Proposal is superseded')
    model, column = ((ApplicationReviewPreview, PrivateReviewOrderLink.preview_id)
                     if payload.document_kind == 'archive'
                     else (OriginalFormReviewCandidate, PrivateReviewOrderLink.candidate_id))
    if session.scalar(select(model.id).where(model.id == payload.document_id, model.tenant_id == tenant_id)) is None:
        raise HTTPException(404, 'Document not found')
    if session.scalar(select(PrivateReviewOrderLink.id).where(
        PrivateReviewOrderLink.tenant_id == tenant_id, column == payload.document_id)) is not None:
        raise HTTPException(409, 'Document already linked; separate correction procedure required')
    kwargs = {'preview_id' if payload.document_kind == 'archive' else 'candidate_id':payload.document_id}
    link = PrivateReviewOrderLink(tenant_id=tenant_id, proposal_id=row.id, evidence_ref=payload.evidence_ref, **kwargs)
    session.add(link)
    try:
        session.flush()
        audit(session, tenant_id, 'retention_link_proposed', detail=link.id)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, 'Concurrent link; refresh') from exc
    return {'link_id':link.id, 'status':'PROPOSED_NOT_APPROVED', 'deletion_authorized':False}


def correct_link(session, tenant_id, payload):
    if not payload.confirm_proposal_only:
        raise HTTPException(409, 'Confirm proposal-only recording')
    _tenant(session, tenant_id, lock=True)
    link = session.scalar(select(PrivateReviewOrderLink).where(
        PrivateReviewOrderLink.tenant_id == tenant_id,
        PrivateReviewOrderLink.id == payload.link_id))
    if link is None:
        raise HTTPException(404, 'Link not found')
    previous = latest_link_correction(session, tenant_id=tenant_id, link_id=link.id)
    revision = previous.revision if previous else 0
    if revision != payload.expected_revision:
        raise HTTPException(409, 'Link revision changed; refresh')
    if revision >= 200:
        raise HTTPException(429, 'Link correction history limit reached')
    target = session.scalar(select(PrivateReviewRetentionProposal).where(
        PrivateReviewRetentionProposal.tenant_id == tenant_id,
        PrivateReviewRetentionProposal.id == payload.proposal_id))
    if target is None:
        raise HTTPException(404, 'Proposal not found')
    current = latest_proposal(session, tenant_id=tenant_id, order_ref=target.order_ref)
    if current is None or current.id != target.id:
        raise HTTPException(409, 'Proposal is superseded')
    if target.id == (previous.proposal_id if previous else link.proposal_id):
        raise HTTPException(409, 'Proposed link already points to this version')
    correction = PrivateReviewLinkCorrection(tenant_id=tenant_id, link_id=link.id,
        proposal_id=target.id, revision=revision+1, evidence_ref=payload.evidence_ref)
    session.add(correction)
    try:
        session.flush()
        audit(session, tenant_id, 'retention_link_corrected', detail=correction.id)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, 'Concurrent correction; refresh') from exc
    return {'correction_id': correction.id, 'link_id': link.id, 'revision': correction.revision,
            'status': 'PROPOSED_NOT_APPROVED', 'deletion_authorized': False,
            'access_change_authorized': False}


def correction_history(session, tenant_id, link_id):
    _tenant(session, tenant_id)
    link = session.scalar(select(PrivateReviewOrderLink).where(
        PrivateReviewOrderLink.tenant_id == tenant_id,
        PrivateReviewOrderLink.id == link_id))
    if link is None:
        raise HTTPException(404, 'Link not found')
    rows = list(session.scalars(select(PrivateReviewLinkCorrection).where(
        PrivateReviewLinkCorrection.tenant_id == tenant_id,
        PrivateReviewLinkCorrection.link_id == link.id
    ).order_by(PrivateReviewLinkCorrection.revision).limit(201)))
    if len(rows) > 200:
        raise HTTPException(409, 'Correction history exceeds limit')
    history = [{'revision': 0, 'proposal_id': link.proposal_id, 'evidence_ref': link.evidence_ref,
                'recorded_at': link.recorded_at.isoformat()}]
    history.extend({'revision': row.revision, 'proposal_id': row.proposal_id, 'evidence_ref': row.evidence_ref,
                    'recorded_at': row.recorded_at.isoformat()} for row in rows)
    return {'link_id': link.id, 'history': history, 'status': 'PROPOSED_NOT_APPROVED',
            'deletion_authorized': False}
