"""User-provided originals, explicitly NOT authenticated marketplace downloads."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import defer

from src.modules.saas_foundation import commercial_capture as capture
from src.modules.saas_foundation.commercial_attachment_bytes import inspect_attachment
from src.modules.saas_foundation.models import (
    CommercialAttachmentEvidence,
    CommercialCaptureAttempt,
    SaasTenant,
)
from src.modules.saas_foundation.service import _aware, audit

MAX_RECORDS_PER_TENANT = 100


def _candidate(session, principal, case_id, attempt_id, candidate_id):
    parent = capture.recheck(session, principal, case_id, attempt_id)
    if not parent['original_reverified']:
        raise HTTPException(409,'Verified historical card required')
    candidate = next((x for x in parent['attachment_inventory']['candidates'] if x['candidate_id']==candidate_id), None)
    if not candidate:
        raise HTTPException(404,'Candidate not found in saved card')
    return parent,candidate


def _query(principal, case_id, attempt_id):
    return select(CommercialAttachmentEvidence).join(CommercialCaptureAttempt, CommercialCaptureAttempt.id==CommercialAttachmentEvidence.attempt_id).where(CommercialCaptureAttempt.tenant_id==principal.tenant_id, CommercialCaptureAttempt.case_id==case_id, CommercialCaptureAttempt.id==attempt_id).execution_options(populate_existing=True)


def _view(row, case_id, *, reverified=False):
    return {'evidence_id':row.id,'case_id':case_id,'attempt_id':row.attempt_id,'candidate_id':row.candidate_id,
            'source_url':row.source_url,'origin':'USER_SUPPLIED_UNATTESTED','created_at':_aware(row.created_at).isoformat(),
            'inspection':row.inspection_json if reverified else {k:v for k,v in row.inspection_json.items() if k!='text_preview'},'stored_bytes_reverified':reverified,
            'platform_original_verified':False,'full_documents_verified':False,'external_submission_allowed':False}


def _check(row,candidate):
    if row.source_url!=candidate['source_url'] or row.candidate_id!=candidate['candidate_id']:
        raise HTTPException(409,'Stored attachment identity mismatch')
    try:
        checked=inspect_attachment(row.raw_bytes,candidate['format_hint'])
    except ValueError as exc:
        raise HTTPException(409,'Stored attachment format mismatch') from exc
    if checked!=row.inspection_json:
        raise HTTPException(409,'Stored attachment integrity mismatch')


def save(session, principal, case_id, attempt_id, candidate_id, raw):
    capture._authorized(session,principal)
    _,candidate=_candidate(session,principal,case_id,attempt_id,candidate_id)
    try:
        inspection=inspect_attachment(raw,candidate['format_hint'])
    except ValueError as exc:
        raise HTTPException(422,'Unsupported or invalid attachment bytes') from exc
    tenant=session.scalar(select(SaasTenant).where(SaasTenant.tenant_id==principal.tenant_id,SaasTenant.customer_id==principal.customer_id).with_for_update())
    if tenant is None:raise HTTPException(404,'Company not found')
    capture._authorized(session,principal)
    existing=session.scalar(_query(principal,case_id,attempt_id).where(CommercialAttachmentEvidence.candidate_id==candidate_id))
    if existing:
        _check(existing,candidate)
        if existing.raw_bytes!=raw:raise HTTPException(409,'Different bytes already recorded for this snapshot; use a newer observation')
        return _view(existing,case_id,reverified=True)
    count=session.scalar(select(func.count()).select_from(CommercialAttachmentEvidence).join(CommercialCaptureAttempt,CommercialCaptureAttempt.id==CommercialAttachmentEvidence.attempt_id).where(CommercialCaptureAttempt.tenant_id==principal.tenant_id))
    if count>=MAX_RECORDS_PER_TENANT:raise HTTPException(429,'Company attachment storage budget reached')
    row=CommercialAttachmentEvidence(attempt_id=attempt_id,member_id=principal.member_id,candidate_id=candidate_id,source_url=candidate['source_url'],raw_bytes=raw,inspection_json=inspection)
    session.add(row);session.flush()
    audit(session,principal.tenant_id,'commercial_user_attachment_saved',principal.member_id,detail=row.id)
    session.commit()
    return _view(row,case_id,reverified=True)


def list_evidence(session,principal,case_id,attempt_id):
    parent=capture.recheck(session,principal,case_id,attempt_id)
    if not parent['original_reverified']:raise HTTPException(409,'Verified historical card required')
    rows=list(session.scalars(_query(principal,case_id,attempt_id).options(defer(CommercialAttachmentEvidence.raw_bytes)).order_by(CommercialAttachmentEvidence.created_at,CommercialAttachmentEvidence.id)))
    return {'customer_id':principal.customer_id,'case_id':case_id,'attempt_id':attempt_id,'items':[_view(r,case_id) for r in rows],'platform_original_verified':False}


def read(session,principal,case_id,attempt_id,candidate_id,previous_attempt_id=None):
    parent,candidate=_candidate(session,principal,case_id,attempt_id,candidate_id)
    row=session.scalar(_query(principal,case_id,attempt_id).where(CommercialAttachmentEvidence.candidate_id==candidate_id))
    if not row:raise HTTPException(404,'Attachment evidence not found')
    _check(row,candidate)
    result=_view(row,case_id,reverified=True)
    if previous_attempt_id is not None:
        previous,old_candidate=_candidate(session,principal,case_id,previous_attempt_id,candidate_id)
        if datetime.fromisoformat(previous['receipt']['observed_at'])>=datetime.fromisoformat(parent['receipt']['observed_at']):raise HTTPException(422,'Previous observation must be older')
        older=session.scalar(_query(principal,case_id,previous_attempt_id).where(CommercialAttachmentEvidence.candidate_id==candidate_id))
        if not older:raise HTTPException(404,'Previous attachment evidence not found')
        _check(older,old_candidate)
        result['comparison']={'previous_attempt_id':previous_attempt_id,'previous_sha256':older.inspection_json['sha256'],'current_sha256':row.inspection_json['sha256'],'supplied_bytes_changed':older.raw_bytes!=row.raw_bytes,'platform_document_version_verified':False}
    return result
