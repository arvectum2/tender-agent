"""Private read-only documentary readiness; no official registry or legal assertion."""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.company_profile_store.models import (
    CompanyDocument,
    CompanyDocumentVersion,
)
from src.modules.company_profile_store.service import list_current_company_profile_facts
from src.modules.customer_registry.models import CustomerProfile
from src.modules.document_store.models import ArtifactVersion, DocumentArtifact
from src.shared.errors import NotFoundError

_KIND_GROUP={'registry':'IDENTITY','sme':'OTHER','tax':'OTHER','license':'LICENSE',
             'certificate':'CERTIFICATE','sro':'OTHER','experience':'EXPERIENCE'}
_DOC_TYPES={'registry':{'STATUTORY','REQUISITES'},'sme':{'STATUTORY','REQUISITES'},
            'tax':{'REQUISITES','STATUTORY'},'license':{'LICENSE'},'certificate':{'CERTIFICATE'},
            'sro':{'CERTIFICATE'},'experience':{'EXPERIENCE'}}
_MAX_AGE={'registry':30,'sme':30,'tax':30,'license':90,'certificate':90,'sro':90,'experience':90}
_CODE=r'^[a-z0-9][a-z0-9_:-]{0,63}$'
_SHA=r'^[a-f0-9]{64}$'


class EvidenceClaim(BaseModel):
    model_config=ConfigDict(extra='forbid')
    schema_version: Literal['qualification-documentary-claim-v1']
    inn: str=Field(pattern=r'^(?:\d{10}|\d{12})$')
    requirement_code: str=Field(pattern=_CODE)
    observed_on: date
    valid_through: date
    owner_confirmed: StrictBool
    assertion: Literal['PRESENT','ABSENT']
    document_key: str=Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,127}$')
    document_version: int=Field(ge=1,strict=True)
    sha256: str=Field(pattern=_SHA)


def _date_utc(dt):
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _document_state(session,customer_id,claim,kind,now,root):
    doc=session.scalar(select(CompanyDocument).where(CompanyDocument.customer_id==customer_id,
                                                     CompanyDocument.document_key==claim.document_key))
    if not doc or doc.document_type not in _DOC_TYPES[kind]:
        return 'DOCUMENT_MISSING_OR_WRONG_TYPE'
    ver=session.scalar(select(CompanyDocumentVersion).where(CompanyDocumentVersion.company_document_id==doc.id)
                       .order_by(CompanyDocumentVersion.version_no.desc()).limit(1))
    if not ver or ver.version_no!=claim.document_version:
        return 'DOCUMENT_VERSION_CHANGED'
    if ver.expires_at and _date_utc(ver.expires_at)<=now:
        return 'DOCUMENT_EXPIRED'
    if ver.issued_at and _date_utc(ver.issued_at).date()>claim.observed_on:
        return 'DOCUMENT_DATE_INCONSISTENT'
    artifact=session.scalar(select(DocumentArtifact).where(DocumentArtifact.artifact_ref==doc.artifact_ref))
    av=session.scalar(select(ArtifactVersion).where(ArtifactVersion.artifact_ref==doc.artifact_ref,
                                                   ArtifactVersion.version_no==ver.artifact_version_no))
    if (not artifact or artifact.deal_id is not None or artifact.current_version!=ver.artifact_version_no
            or not av or av.checksum_sha256!=claim.sha256 or artifact.checksum_sha256!=claim.sha256):
        return 'ARTIFACT_BINDING_MISMATCH'
    try:
        base=root.resolve()/'company-onboarding'/customer_id
        p=Path(av.storage_uri)
        if (not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',customer_id) or base.is_symlink()
                or base.parent.is_symlink() or p.is_symlink() or p.parent.resolve()!=base.resolve()
                or not p.is_file() or p.suffix.lower()!='.pdf'):
            return 'DOCUMENT_OUTSIDE_PRIVATE_STORE'
        with p.open('rb') as f:
            raw=f.read(10*1024*1024+1)
        if not raw.startswith(b'%PDF-') or len(raw)>10*1024*1024 or hashlib.sha256(raw).hexdigest()!=claim.sha256:
            return 'DOCUMENT_BYTES_MISMATCH'
    except (ValueError,OSError,TypeError):
        return 'DOCUMENT_UNAVAILABLE'
    return 'DOCUMENT_BYTES_MATCH'


def review_profile(session: Session, *, customer_id: str, root: Path, requirements: dict[str,str], now: datetime | None=None):
    """Caller supplies already-authorized customer and reviewed requirement codes.
    Only a claimed fact plus exact current document bytes is a review candidate.
    """
    now=_date_utc(now or datetime.now(UTC))
    customer=session.scalar(select(CustomerProfile).where(CustomerProfile.customer_id==customer_id))
    if customer is None:
        raise NotFoundError('Customer not found')
    if len(requirements)>64 or any(k not in _KIND_GROUP or not re.fullmatch(_CODE,c)
                                   for c,k in requirements.items()):
        raise ValueError('Invalid bounded requirement codes')
    facts={f.fact_key:f for f in list_current_company_profile_facts(session,customer_id=customer_id)}
    rows=[]
    for code,kind in requirements.items():
        record=facts.get('qualification_claim:'+code)
        row={'requirement_code':code,'kind':kind,'state':'MISSING','claim_assertion':None,
             'fact_version':record.version_no if record else None,'document_key':None,
             'semantic_verified':False,'legal_satisfied':None}
        if record is not None:
            if not record.expires_at or _date_utc(record.expires_at)<=now:
                row['state']='EXPIRED_OR_NO_EXPIRY'
            elif record.fact_group!=_KIND_GROUP[kind] or record.source_type!='OWNER_CONFIRMED':
                row['state']='UNREVIEWED_FACT'
            else:
                try:
                    claim=EvidenceClaim.model_validate(record.value_json)
                except ValidationError:
                    row['state']='INVALID_CLAIM'
                else:
                    if (not claim.owner_confirmed or claim.inn!=customer.inn or claim.requirement_code!=code
                            or not claim.observed_on<=now.date()<=claim.valid_through
                            or (now.date()-claim.observed_on).days>_MAX_AGE[kind]
                            or claim.valid_through<claim.observed_on):
                        row['state']='IDENTITY_SCOPE_OR_DATE_UNCONFIRMED'
                    else:
                        row['document_key']=claim.document_key
                        state=_document_state(session,customer_id,claim,kind,now,root)
                        row['state']=state
                        if state=='DOCUMENT_BYTES_MATCH':
                            row.update(state='DOCUMENTED_OWNER_CLAIM_REVIEW_REQUIRED',claim_assertion=claim.assertion,
                                       fact_source_ref=record.source_ref,document_version=claim.document_version,
                                       document_sha256=claim.sha256,observed_on=claim.observed_on.isoformat())
        rows.append(row)
    profile=facts.get('supplier_profile')
    screening_state='MISSING'
    if profile:
        screening_state='UNAVAILABLE'
        if profile.fact_group=='OTHER' and profile.source_type in {'OWNER_CONFIRMED','CUSTOMER_PROVIDED'} and (not profile.expires_at or _date_utc(profile.expires_at)>now):
            from src.modules.customer_onboarding.router import OnboardingProfile

            try:
                OnboardingProfile.model_validate(profile.value_json)
            except ValidationError:
                pass
            else:
                screening_state='OWNER_INPUT_REVIEW_REQUIRED'
    return {'status':'PROFILE_DOCUMENTARY_READINESS_ONLY','customer_id':customer_id,
            'assessment_date':now.date().isoformat(),'screening_preferences_state':screening_state,
            'requirements':rows,'documented_claim_count':sum(r['state']=='DOCUMENTED_OWNER_CLAIM_REVIEW_REQUIRED' for r in rows),
            'official_registry_checked':False,'legal_eligibility':'NOT_ASSESSED','current_supplier_qualification_verified':False,
            'recommendation':'DEFER','go_eligible':False,'external_action_allowed':False}
