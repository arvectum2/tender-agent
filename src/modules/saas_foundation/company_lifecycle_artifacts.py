"""Bounded copies of receipt/protocol files attached to immutable lifecycle events.

A byte match, format check or file name cannot verify an event on an ETP.
"""
from __future__ import annotations

from typing import Literal

from fastapi import HTTPException
from sqlalchemy import func, select

from src.modules.saas_foundation import company_lifecycle as lifecycle
from src.modules.saas_foundation import company_portfolio as portfolio
from src.modules.saas_foundation import company_readiness as readiness
from src.modules.saas_foundation.commercial_attachment_bytes import inspect_attachment
from src.modules.saas_foundation.models import (
    CompanyCaseLifecycleEvent,
    CompanyLifecycleArtifact,
    SaasMember,
)
from src.modules.saas_foundation.service import audit, legal_required, role_required

ArtifactFormat = Literal['pdf','docx','xlsx']
MAX_ARTIFACTS_PER_TENANT = 100


def _event(session,principal,case_id,event_id):
    legal_required(session,principal)
    portfolio._owned_case(session,principal,case_id)
    event=session.scalar(lifecycle._events(principal,case_id).where(CompanyCaseLifecycleEvent.id==event_id))
    if event is None:raise HTTPException(404,'Lifecycle event not found')
    if event.stage not in lifecycle.OUTCOMES|{'SUBMITTED'}:raise HTTPException(409,'External event required')
    return event


def _kind(event):
    return 'SUBMISSION_RECEIPT' if event.stage=='SUBMITTED' else 'OUTCOME_PROTOCOL'


def _artifact(session,event):
    return session.scalar(select(CompanyLifecycleArtifact).where(CompanyLifecycleArtifact.lifecycle_event_id==event.id).execution_options(populate_existing=True))


def _inspect(raw,kind):
    try:return inspect_attachment(raw,kind)
    except ValueError as exc:raise HTTPException(422,'Invalid or unsupported artifact bytes') from exc


def _check(row,event):
    try:inspection=inspect_attachment(row.raw_bytes,row.format_hint)
    except ValueError as exc:raise HTTPException(409,'Stored artifact format mismatch') from exc
    if row.artifact_kind!=_kind(event) or row.lifecycle_event_id!=event.id or inspection!=row.inspection_json:
        raise HTTPException(409,'Stored lifecycle artifact integrity mismatch')
    return inspection


def _view(principal,event,row,inspection):
    return {'customer_id':principal.customer_id,'case_id':event.case_id,'event_id':event.id,'event_revision':event.revision,'event_stage':event.stage,'artifact_id':row.id,'member_id':row.member_id,'artifact_kind':row.artifact_kind,'format_hint':row.format_hint,'created_at':portfolio._utc(row.created_at),'inspection':{k:v for k,v in inspection.items() if k!='text_preview'},'origin':'USER_SUPPLIED_UNATTESTED','stored_bytes_reverified':True,'platform_original_verified':False,'external_fact_verified':False,'external_submission_allowed':False}


def save(session,principal,case_id,event_id,raw,format_hint):
    role_required(principal,'owner','admin')
    event=_event(session,principal,case_id,event_id)
    inspection=_inspect(raw,format_hint)
    # The tenant lock is shared with other bounded evidence writers.
    portfolio._owned_case(session,principal,case_id,lock=True);readiness.lock_tenant(session,principal)
    member=session.get(SaasMember,principal.member_id,populate_existing=True)
    if not member or member.role not in {'owner','admin'}:raise HTTPException(403,'Current manager permission required')
    event=_event(session,principal,case_id,event_id)
    row=_artifact(session,event)
    if row:
        previous=_check(row,event)
        if row.raw_bytes!=raw or row.format_hint!=format_hint:raise HTTPException(409,'Different artifact already bound to immutable event')
        return _view(principal,event,row,previous)
    count=session.scalar(select(func.count()).select_from(CompanyLifecycleArtifact).join(CompanyCaseLifecycleEvent,CompanyCaseLifecycleEvent.id==CompanyLifecycleArtifact.lifecycle_event_id).where(CompanyCaseLifecycleEvent.tenant_id==principal.tenant_id))
    if count>=MAX_ARTIFACTS_PER_TENANT:raise HTTPException(429,'Lifecycle artifact budget reached')
    row=CompanyLifecycleArtifact(lifecycle_event_id=event.id,member_id=principal.member_id,artifact_kind=_kind(event),format_hint=format_hint,raw_bytes=raw,inspection_json=inspection)
    session.add(row);session.flush();audit(session,principal.tenant_id,'company_lifecycle_artifact_saved',principal.member_id,detail=row.id);session.commit()
    return _view(principal,event,row,inspection)


def read(session,principal,case_id,event_id):
    event=_event(session,principal,case_id,event_id)
    row=_artifact(session,event)
    if row is None:raise HTTPException(404,'Lifecycle artifact not found')
    return _view(principal,event,row,_check(row,event))


def download(session,principal,case_id,event_id):
    event=_event(session,principal,case_id,event_id)
    row=_artifact(session,event)
    if row is None:raise HTTPException(404,'Lifecycle artifact not found')
    inspection=_check(row,event)
    return bytes(row.raw_bytes), row.format_hint, inspection['sha256']
