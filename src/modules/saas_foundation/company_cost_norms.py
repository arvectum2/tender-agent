"""Explicit internal manager approvals, never automatic bid assumptions."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.modules.saas_foundation import company_actual_samples as samples
from src.modules.saas_foundation import company_portfolio as portfolio
from src.modules.saas_foundation import company_price_scenarios as price
from src.modules.saas_foundation.commercial_capture import _authorized
from src.modules.saas_foundation.company_actual_costs import Digest
from src.modules.saas_foundation.models import CompanyCostNormVersion as Version
from src.modules.saas_foundation.models import SaasMember, SaasTenant
from src.modules.saas_foundation.service import audit, role_required


class Proposal(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    sample: samples.PreviewInput
    norm_quantity: price.Quantity
    norm_rate_rub: price.Money
    rationale: str=Field(min_length=10,max_length=2000)
    confirm_reported_source_limits: Literal[True]

    @model_validator(mode='after')
    def positive_quantity(self):
        if Decimal(self.norm_quantity)<=0:raise ValueError('Positive normative quantity required')
        return self


class Approval(BaseModel):
    model_config=ConfigDict(extra='forbid')
    proposal: Proposal
    preview_sha256: Digest
    expected_revision: int=Field(ge=0,le=100,strict=True)
    idempotency_key: str=Field(min_length=8,max_length=128)
    confirm_internal_approval: Literal[True]


class Withdrawal(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    expected_revision: int=Field(ge=1,le=100,strict=True)
    idempotency_key: str=Field(min_length=8,max_length=128)
    rationale: str=Field(min_length=10,max_length=2000)
    confirm_withdrawal: Literal[True]


def sha(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def norm_key(payload):
    return sha([payload.category,samples.label(payload.title),payload.unit])


def _query(principal):
    return select(Version).where(Version.tenant_id==principal.tenant_id)


def _access(session,principal,write=False):
    role_required(principal,*(['owner','admin'] if write else ['owner','admin','analyst']))
    if write:
        session.scalar(select(SaasTenant).where(SaasTenant.tenant_id==principal.tenant_id).with_for_update())
    _authorized(session,principal)
    if write:
        member=session.get(SaasMember,principal.member_id,populate_existing=True)
        if not member or member.role not in {'owner','admin'}:raise HTTPException(403,'Current manager permission required')


def _latest(session,principal,key):
    return session.scalar(_query(principal).where(Version.norm_key==key).order_by(Version.revision.desc()).limit(1).execution_options(populate_existing=True))


def _seal(row):
    return sha({'norm_id':row.id,'created_at':portfolio._utc(row.created_at).isoformat() if isinstance(portfolio._utc(row.created_at),datetime) else portfolio._utc(row.created_at),'tenant_id':row.tenant_id,'member_id':row.member_id,'norm_key':row.norm_key,'revision':row.revision,'action':row.action,'idempotency_key':row.idempotency_key,'inputs':row.input_json,'result':row.result_json})


def _view(principal,row):
    if row.record_sha256!=_seal(row):raise HTTPException(409,'Stored corporate norm integrity mismatch')
    return {'schema':'company_cost_norm_version_v1','customer_id':principal.customer_id,'norm_id':row.id,'norm_key':row.norm_key,'revision':row.revision,'action':row.action,'member_id':row.member_id,'created_at':portfolio._utc(row.created_at),'record_sha256':row.record_sha256,'inputs':row.input_json,'result':row.result_json,'external_submission_allowed':False,'automatically_applied':False}


def _preview(session,principal,proposal):
    key=norm_key(proposal.sample)
    current=_latest(session,principal,key)
    if current:_view(principal,current)
    chosen=samples.preview(session,principal,proposal.sample)
    return {'schema':'company_cost_norm_preview_v1','customer_id':principal.customer_id,'norm_key':key,'expected_revision':current.revision if current else 0,'proposal':proposal.model_dump(mode='json'),'sample_observation':chosen,'approved_norm':False,'automatically_applied':False,'inputs_stored':False,'external_submission_allowed':False}


def preview(session,principal,proposal):
    _access(session,principal)
    result=_preview(session,principal,proposal)
    return {**result,'preview_sha256':sha(result)}


def _replay(session,principal,key,action,payload):
    row=session.scalar(_query(principal).where(Version.idempotency_key==payload.idempotency_key))
    if not row:return None
    if row.norm_key!=key or row.action!=action or row.member_id!=principal.member_id or row.input_json!=payload.model_dump(mode='json'):
        raise HTTPException(409,'Conflicting norm replay')
    return _view(principal,row)


def _store(session,principal,key,action,payload,result):
    row=Version(id=str(uuid4()),created_at=datetime.now(UTC),tenant_id=principal.tenant_id,member_id=principal.member_id,norm_key=key,revision=payload.expected_revision+1,action=action,idempotency_key=payload.idempotency_key,input_json=payload.model_dump(mode='json'),result_json=result,record_sha256='')
    row.record_sha256=_seal(row)
    try:
        session.add(row);session.flush()
        audit(session,principal.tenant_id,'company_cost_norm_'+action.lower(),principal.member_id,detail=row.id)
        session.commit()
    except IntegrityError as exc:
        session.rollback();raise HTTPException(409,'Concurrent norm decision; refresh') from exc
    return _view(principal,row)


def approve(session,principal,payload):
    _access(session,principal,write=True)
    key=norm_key(payload.proposal.sample)
    replay=_replay(session,principal,key,'APPROVED',payload)
    if replay:return replay
    for ref in sorted(payload.proposal.sample.samples,key=lambda r:r.case_id):
        portfolio._owned_case(session,principal,ref.case_id,lock=True)
    view=_preview(session,principal,payload.proposal)
    if view['expected_revision']!=payload.expected_revision or sha(view)!=payload.preview_sha256:
        raise HTTPException(409,'Norm preview changed; refresh')
    if payload.expected_revision>=99:raise HTTPException(429,'Norm approval limit reached; withdrawal reserved')
    if payload.expected_revision==0:
        count=session.scalar(select(func.count(func.distinct(Version.norm_key))).where(Version.tenant_id==principal.tenant_id))
        if count>=500:raise HTTPException(429,'Norm key limit reached')
    result={'category':payload.proposal.sample.category,'title':payload.proposal.sample.title,'unit':payload.proposal.sample.unit,'currency':'RUB','norm_quantity':payload.proposal.norm_quantity,'norm_rate_rub':payload.proposal.norm_rate_rub,'rationale':payload.proposal.rationale,'sample_observation':view['sample_observation'],'preview_sha256':payload.preview_sha256,'origin':'EXPLICIT_INTERNAL_MANAGER_APPROVAL','approved_norm':True,'actual_amounts_independently_verified':False,'automatically_applied':False,'external_submission_allowed':False}
    return _store(session,principal,key,'APPROVED',payload,result)


def withdraw(session,principal,key,payload):
    _access(session,principal,write=True)
    replay=_replay(session,principal,key,'WITHDRAWN',payload)
    if replay:return replay
    current=_latest(session,principal,key)
    if not current:raise HTTPException(404,'Norm not found')
    previous=_view(principal,current)
    if current.action!='APPROVED' or current.revision!=payload.expected_revision:raise HTTPException(409,'Norm version changed or already withdrawn')
    if current.revision>=100:raise HTTPException(429,'Norm version limit reached')
    result={k:previous['result'][k] for k in ('category','title','unit','currency')}
    result.update(rationale=payload.rationale,withdrawn_norm_id=current.id,withdrawn_record_sha256=current.record_sha256,approved_norm=False,automatically_applied=False,external_submission_allowed=False)
    return _store(session,principal,key,'WITHDRAWN',payload,result)


def history(session,principal,key,offset,limit):
    _access(session,principal)
    rows=list(session.scalars(_query(principal).where(Version.norm_key==key).order_by(Version.revision.desc()).offset(offset).limit(limit+1)))
    if not rows and offset==0:raise HTTPException(404,'Norm not found')
    return {'customer_id':principal.customer_id,'norm_key':key,'items':[_view(principal,r) for r in rows[:limit]],'has_more':len(rows)>limit}


def catalog(session,principal,offset,limit):
    _access(session,principal)
    latest=select(Version.norm_key,func.max(Version.revision).label('revision')).where(Version.tenant_id==principal.tenant_id).group_by(Version.norm_key).subquery()
    rows=list(session.scalars(_query(principal).join(latest,(Version.norm_key==latest.c.norm_key)&(Version.revision==latest.c.revision)).order_by(Version.norm_key).offset(offset).limit(limit+1)))
    return {'customer_id':principal.customer_id,'items':[_view(principal,r) for r in rows[:limit]],'has_more':len(rows)>limit}
