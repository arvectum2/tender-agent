"""Human review ledger on literal source fragments, with scoped version bindings.

Neither a reference-list claim nor a recorded document establishes compliance.
No automatic verdict, model execution, marketplace request or new source bytes.
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from src.modules.company_profile_store.models import (
    CompanyDocument,
    CompanyDocumentVersion,
    CompanyProfileFactVersion,
)
from src.modules.company_profile_store.qualification_references import (
    REFERENCE_FACT_KEY,
    CompletedContractReferenceSnapshot,
)
from src.modules.company_profile_store.service import fact_state
from src.modules.customer_onboarding.router import OnboardingProfile
from src.modules.saas_foundation import commercial_attachment_service as attachments
from src.modules.saas_foundation import commercial_capture as capture
from src.modules.saas_foundation.commercial_text_evidence import project_text
from src.modules.saas_foundation.company_case_evidence import _latest_profile
from src.modules.saas_foundation.models import (
    CommercialAttachmentEvidence,
    CommercialRequirementReview,
    SaasTenant,
)
from src.modules.saas_foundation.service import _aware, audit, now_utc

MAX_REVISIONS=20
MAX_DOCUMENT_OPTIONS=50


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fragment_key: str = Field(pattern=r'^[0-9a-f]{64}$')
    expected_revision: int = Field(ge=0, le=MAX_REVISIONS)
    profile_fact_id: str = Field(min_length=1,max_length=64)
    reference_fact_id: str | None = Field(default=None,max_length=64)
    document_version_id: str | None = Field(default=None,max_length=64)
    assessment: Literal['NOT_REQUIREMENT','NEEDS_EVIDENCE','HUMAN_SUPPORT_RECORDED','HUMAN_GAP_RECORDED']
    rationale: str = Field(min_length=1,max_length=2000)
    idempotency_key: str = Field(min_length=8,max_length=128)

    @model_validator(mode='after')
    def validate_review(self):
        self.rationale=self.rationale.strip()
        if not self.rationale:
            raise ValueError('Review rationale required')
        if self.assessment=='HUMAN_SUPPORT_RECORDED' and not (self.reference_fact_id or self.document_version_id):
            raise ValueError('Support requires an explicit company evidence reference')
        if self.assessment=='NOT_REQUIREMENT' and (self.reference_fact_id or self.document_version_id):
            raise ValueError('Non-requirement must not bind qualification evidence')
        return self


def _source(session,principal,case_id,attempt_id,candidate_id):
    capture._authorized(session,principal)
    _,candidate=attachments._candidate(session,principal,case_id,attempt_id,candidate_id)
    row=session.scalar(attachments._query(principal,case_id,attempt_id).where(CommercialAttachmentEvidence.candidate_id==candidate_id))
    if not row:raise HTTPException(404,'Attachment evidence not found')
    attachments._check(row,candidate)
    if candidate['format_hint'] not in {'docx','xlsx'}:
        raise HTTPException(409,'Stable DOCX/XLSX source projection required for review')
    projection=project_text(row.raw_bytes,candidate['format_hint'])
    fragments={f['fragment_id']:f for f in projection['fragments']}
    items={}
    for match in projection['requirement_candidates']:
        fragment=fragments[match['fragment_id']]
        # Never let an incomplete excerpt be affirmed as a complete requirement.
        if fragment['fragment_truncated']:continue
        info={'schema':projection['schema'],'source_sha256':projection['source_sha256'],'location':fragment['location'],'text':fragment['text'],'categories':match['categories']}
        key=hashlib.sha256(json.dumps(info,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        items[key]=info
    return row,items


def _reference(session,principal):
    return session.scalar(select(CompanyProfileFactVersion).where(CompanyProfileFactVersion.customer_id==principal.customer_id,CompanyProfileFactVersion.fact_key==REFERENCE_FACT_KEY).order_by(CompanyProfileFactVersion.version_no.desc()).limit(1).execution_options(populate_existing=True))


def _reference_info(row):
    if row is None:return None
    state=fact_state(row,latest_version_no=row.version_no)[2]
    valid=False;count=None;completeness=None
    if row.fact_group=='EXPERIENCE' and row.source_type in {'CUSTOMER_PROVIDED','OWNER_CONFIRMED'}:
        try:
            snapshot=CompletedContractReferenceSnapshot.model_validate(row.value_json)
            valid=True;count=len(snapshot.contracts);completeness=snapshot.completeness
        except ValueError:pass
    return {'fact_id':row.id,'version':row.version_no,'state':state,'selectable':valid and state=='ACTIVE','declared_count':count,'completeness':completeness,'original_contracts_verified':False}


def _document_query(principal):
    return select(CompanyDocument,CompanyDocumentVersion).join(CompanyDocumentVersion,CompanyDocumentVersion.company_document_id==CompanyDocument.id).where(CompanyDocument.customer_id==principal.customer_id)


def _document_info(doc,version):
    return {'document_id':doc.id,'document_version_id':version.id,'document_key':doc.document_key,'display_name':doc.display_name,'document_type':doc.document_type,'version':version.version_no,'state':'EXPIRED' if version.expires_at and _aware(version.expires_at)<=now_utc() else 'ACTIVE','document_bytes_verified':False}


def _current_document(session,principal,version_id):
    row=session.execute(_document_query(principal).where(CompanyDocumentVersion.id==version_id)).one_or_none()
    if not row:return None
    doc,version=row
    latest=session.scalar(select(CompanyDocumentVersion).where(CompanyDocumentVersion.company_document_id==doc.id).order_by(CompanyDocumentVersion.version_no.desc()).limit(1).execution_options(populate_existing=True))
    info=_document_info(doc,version)
    if latest.id!=version.id:info['state']='SUPERSEDED'
    return info


def _profile_info(profile):
    if not profile:return None
    state=fact_state(profile,latest_version_no=profile.version_no)[2]
    try:OnboardingProfile.model_validate(profile.value_json)
    except ValueError:state='INVALID'
    return {'fact_id':profile.id,'version':profile.version_no,'state':state}


def _view(session,principal,row,profile,reference):
    stale=[]
    if not profile or profile['fact_id']!=row.profile_fact_id or profile['state']!='ACTIVE':stale.append('PROFILE_CHANGED_OR_INACTIVE')
    if row.reference_fact_id and (not reference or reference['fact_id']!=row.reference_fact_id or not reference['selectable']):stale.append('REFERENCE_LIST_CHANGED_OR_INACTIVE')
    if row.document_version_id:
        doc=_current_document(session,principal,row.document_version_id)
        if not doc or doc['state']!='ACTIVE':stale.append('DOCUMENT_CHANGED_OR_INACTIVE')
    return {'review_id':row.id,'fragment_key':row.fragment_key,'revision':row.revision,'member_id':row.member_id,'created_at':_aware(row.created_at).isoformat(),'profile_fact_id':row.profile_fact_id,'reference_fact_id':row.reference_fact_id,'document_version_id':row.document_version_id,'assessment':row.review_json['input']['assessment'],'rationale':row.review_json['input']['rationale'],'fragment':row.review_json['fragment'],'stale_reasons':stale,'qualification_verified':False,'external_submission_allowed':False}


def _reviews(attachment_id):
    return select(CommercialRequirementReview).where(CommercialRequirementReview.attachment_id==attachment_id)


def matrix(session,principal,case_id,attempt_id,candidate_id):
    attachment,items=_source(session,principal,case_id,attempt_id,candidate_id)
    profile=_profile_info(_latest_profile(session,principal));reference=_reference_info(_reference(session,principal))
    rows=list(session.scalars(_reviews(attachment.id).order_by(CommercialRequirementReview.revision.desc())))
    latest={}
    for row in rows:latest.setdefault(row.fragment_key,row)
    docs=[];seen=set()
    for doc,ver in session.execute(_document_query(principal).order_by(CompanyDocument.id,CompanyDocumentVersion.version_no.desc()).limit(501)):
        if doc.id in seen:continue
        seen.add(doc.id)
        if len(docs)>=MAX_DOCUMENT_OPTIONS:break
        docs.append(_document_info(doc,ver))
    result=[]
    for key,fragment in items.items():
        review=_view(session,principal,latest[key],profile,reference) if key in latest else None
        if review and review['fragment']!=fragment:raise HTTPException(409,'Review source binding mismatch')
        result.append({'fragment_key':key,'fragment':fragment,'review':review,'revision':review['revision'] if review else 0})
    if set(latest)-set(items):raise HTTPException(409,'Historical requirement source no longer resolves')
    return {'customer_id':principal.customer_id,'case_id':case_id,'attempt_id':attempt_id,'candidate_id':candidate_id,'attachment_id':attachment.id,'profile':profile,'reference_list':reference,'document_options':docs,'document_options_complete':False,'items':result,'summary':{'unreviewed':sum(x['review'] is None for x in result),'needs_evidence':sum(x['review'] is not None and (x['review']['assessment']=='NEEDS_EVIDENCE' or bool(x['review']['stale_reasons'])) for x in result),'human_gap_recorded':sum(x['review'] is not None and x['review']['assessment']=='HUMAN_GAP_RECORDED' and not x['review']['stale_reasons'] for x in result)},'coverage_complete':False,'platform_original_verified':False,'qualification_verified':False,'external_submission_allowed':False}


def submit(session,principal,case_id,attempt_id,candidate_id,payload):
    attachment,items=_source(session,principal,case_id,attempt_id,candidate_id)
    fragment=items.get(payload.fragment_key)
    if fragment is None:raise HTTPException(404,'Reviewable source fragment not found')
    tenant=session.scalar(select(SaasTenant).where(SaasTenant.tenant_id==principal.tenant_id,SaasTenant.customer_id==principal.customer_id).with_for_update())
    if tenant is None:raise HTTPException(404,'Company not found')
    capture._authorized(session,principal)
    profile=_profile_info(_latest_profile(session,principal));reference=_reference_info(_reference(session,principal))
    replay=session.scalar(_reviews(attachment.id).where(CommercialRequirementReview.idempotency_key==payload.idempotency_key))
    if replay:
        if replay.review_json!={'input':payload.model_dump(mode='json'),'fragment':fragment}:raise HTTPException(409,'Idempotency key reused')
        return _view(session,principal,replay,profile,reference)
    if not profile or profile['state']!='ACTIVE' or profile['fact_id']!=payload.profile_fact_id:raise HTTPException(409,'Active profile version changed or missing')
    if payload.reference_fact_id and (not reference or not reference['selectable'] or reference['fact_id']!=payload.reference_fact_id):raise HTTPException(409,'Current owned reference list required')
    if payload.document_version_id:
        doc=_current_document(session,principal,payload.document_version_id)
        if not doc or doc['state']!='ACTIVE':raise HTTPException(409,'Current owned document version required')
    previous=session.scalar(_reviews(attachment.id).where(CommercialRequirementReview.fragment_key==payload.fragment_key).order_by(CommercialRequirementReview.revision.desc()).limit(1))
    revision=previous.revision if previous else 0
    if revision!=payload.expected_revision:raise HTTPException(409,'Requirement review revision changed')
    if revision>=MAX_REVISIONS:raise HTTPException(429,'Review history limit reached')
    row=CommercialRequirementReview(attachment_id=attachment.id,member_id=principal.member_id,fragment_key=payload.fragment_key,revision=revision+1,idempotency_key=payload.idempotency_key,profile_fact_id=payload.profile_fact_id,reference_fact_id=payload.reference_fact_id,document_version_id=payload.document_version_id,review_json={'input':payload.model_dump(mode='json'),'fragment':fragment})
    session.add(row);session.flush();audit(session,principal.tenant_id,'commercial_requirement_review_recorded',principal.member_id,detail=row.id);session.commit()
    return _view(session,principal,row,profile,reference)


def history(session,principal,case_id,attempt_id,candidate_id,fragment_key):
    attachment,items=_source(session,principal,case_id,attempt_id,candidate_id)
    if fragment_key not in items:raise HTTPException(404,'Reviewable source fragment not found')
    profile=_profile_info(_latest_profile(session,principal));reference=_reference_info(_reference(session,principal))
    rows=list(session.scalars(_reviews(attachment.id).where(CommercialRequirementReview.fragment_key==fragment_key).order_by(CommercialRequirementReview.revision.desc())))
    if any(row.review_json['fragment']!=items[fragment_key] for row in rows):raise HTTPException(409,'Review source binding mismatch')
    return {'items':[_view(session,principal,row,profile,reference) for row in rows],'qualification_verified':False}
