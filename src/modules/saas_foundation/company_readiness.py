"""Bounded partial-review snapshot, never an external qualification verdict."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from src.modules.saas_foundation import commercial_capture as capture
from src.modules.saas_foundation import commercial_requirement_review as review
from src.modules.saas_foundation import company_portfolio as portfolio
from src.modules.saas_foundation.models import (
    CommercialCaptureAttempt,
    CompanyReadinessEvidence,
    SaasMember,
    SaasTenant,
)
from src.modules.saas_foundation.service import audit, legal_required, role_required

MAX_DOCS = 3


class BindInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ready_event_id: str = Field(min_length=1,max_length=64)
    projection_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    acknowledge_partial_coverage: Literal[True]


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def lock_tenant(session,principal):
    tenant=session.scalar(select(SaasTenant).where(SaasTenant.tenant_id==principal.tenant_id,SaasTenant.customer_id==principal.customer_id).with_for_update())
    if tenant is None:raise HTTPException(404,'Company not found')
    capture._authorized(session,principal)


def project(session,principal,case_id):
    capture._authorized(session,principal)
    case=portfolio._owned_case(session,principal,case_id)
    if portfolio._view(session,principal,case)['source_kind']!='commercial_reference':
        raise HTTPException(409,'Commercial readiness evidence only in v1')
    attempt=session.scalar(select(CommercialCaptureAttempt).where(CommercialCaptureAttempt.case_id==case_id,CommercialCaptureAttempt.tenant_id==principal.tenant_id).order_by(CommercialCaptureAttempt.created_at.desc(),CommercialCaptureAttempt.id.desc()).limit(1))
    if attempt is None:raise HTTPException(409,'No saved commercial observation')
    matrix=review.case_matrix(session,principal,case_id,attempt.id,limit=MAX_DOCS)
    profile=review._profile_info(review._latest_profile(session,principal));issues=[]
    if not profile or profile['state']!='ACTIVE':issues.append('ACTIVE_PROFILE_REQUIRED')
    if matrix['has_more']:issues.append('DOCUMENT_BOUND_EXCEEDED')
    if matrix['candidate_count']==0:issues.append('NO_DISCOVERED_DOCUMENTS')
    if matrix['missing_copy_count']:issues.append('MISSING_USER_COPIES')
    if matrix['link_scan_truncated']:issues.append('TRUNCATED_LINK_SCAN')
    documents=[];support_count=0
    for doc in matrix['documents']:
        item={'candidate_id':doc['candidate_id'],'evidence_id':doc['stored_evidence_id'],'state':doc['state'],'reviews':[]}
        if doc['state']!='PARTIAL_REVIEW_CANDIDATES':issues.append('DOCUMENT_NOT_REVIEWABLE')
        for candidate in doc['items']:
            r=candidate['review']
            if r is None:issues.append('UNREVIEWED_FRAGMENT')
            elif r['stale_reasons']:issues.append('STALE_REVIEW')
            elif r['assessment'] not in {'HUMAN_SUPPORT_RECORDED','NOT_REQUIREMENT'}:issues.append('UNRESOLVED_REQUIREMENT')
            elif r['assessment']=='HUMAN_SUPPORT_RECORDED':support_count+=1
            # Preserve entire review and literal fragment digest; no inferred support.
            item['reviews'].append({'fragment_key':candidate['fragment_key'],'review':r})
        documents.append(item)
    if not support_count:issues.append('NO_RECORDED_SUPPORT')
    return {'schema':'commercial_readiness_partial_v1','customer_id':principal.customer_id,'case_id':case_id,'attempt_id':attempt.id,'card_sha256':matrix['card_sha256'],'profile':profile,'candidate_count':matrix['candidate_count'],'rejected_or_opaque_links':matrix['rejected_or_opaque_links'],'documents':documents,'issues':sorted(set(issues)),'partial_review_resolved':not issues,'coverage_complete':False,'platform_original_verified':False,'qualification_verified':False,'external_submission_allowed':False}


def _ready(session,principal,case_id):
    from src.modules.saas_foundation import company_lifecycle as lifecycle
    decision=portfolio._latest(session,principal,case_id);event=lifecycle._latest(session,principal,case_id)
    if not decision or decision.action!='GO' or not event or event.stage!='READY' or event.go_decision_id!=decision.id:
        raise HTTPException(409,'Current GO-bound READY event required')
    return event


def _binding(session,event_id):
    return session.scalar(select(CompanyReadinessEvidence).where(CompanyReadinessEvidence.ready_event_id==event_id).execution_options(populate_existing=True))


def _view(binding,projection,event):
    sha=digest(projection)
    if binding and (digest(binding.projection_json)!=binding.projection_sha256 or binding.projection_json.get('attempt_id')!=binding.attempt_id):
        raise HTTPException(409,'Readiness snapshot integrity mismatch')
    return {'ready_event_id':event.id,'projection_sha256':sha,'projection':projection,'binding_id':binding.id if binding else None,'bound_projection_sha256':binding.projection_sha256 if binding else None,'binding_current':bool(binding and binding.projection_sha256==sha and projection['partial_review_resolved']),'qualification_verified':False,'external_submission_allowed':False}


def state(session,principal,case_id):
    legal_required(session,principal);portfolio._owned_case(session,principal,case_id)
    event=_ready(session,principal,case_id)
    return _view(_binding(session,event.id),project(session,principal,case_id),event)


def bind(session,principal,case_id,payload):
    role_required(principal,'owner','admin');legal_required(session,principal)
    portfolio._owned_case(session,principal,case_id,lock=True);lock_tenant(session,principal)
    member=session.get(SaasMember,principal.member_id,populate_existing=True)
    if not member or member.role not in {"owner","admin"}:raise HTTPException(403,"Current manager permission required")
    event=_ready(session,principal,case_id)
    if event.id!=payload.ready_event_id:raise HTTPException(409,'READY event changed')
    projection=project(session,principal,case_id)
    sha=digest(projection)
    if sha!=payload.projection_sha256 or not projection['partial_review_resolved']:raise HTTPException(409,'Partial review changed or unresolved')
    existing=_binding(session,event.id)
    if existing:
        result=_view(existing,projection,event)
        if not result['binding_current']:raise HTTPException(409,'Record a new READY event before rebinding')
        return result
    result=CompanyReadinessEvidence(ready_event_id=event.id,attempt_id=projection['attempt_id'],member_id=principal.member_id,projection_sha256=sha,projection_json=projection)
    session.add(result);session.flush();audit(session,principal.tenant_id,'company_readiness_evidence_bound',principal.member_id,detail=result.id);session.commit()
    return _view(result,projection,event)


def require_current(session,principal,case_id):
    lock_tenant(session,principal)
    if not state(session,principal,case_id)['binding_current']:
        raise HTTPException(409,'Current partial-review readiness binding required')
