"""Named second-member review of immutable historical form bytes; never release."""
from __future__ import annotations

import hashlib
import zipfile
from datetime import timedelta
from typing import Literal

from fastapi import HTTPException
from lxml.etree import XMLSyntaxError
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from src.modules.application_package_generator.checklist_bundle_gate import digest
from src.modules.application_package_generator.original_form_candidate import (
    MAX_BYTES,
    _parts,
    build_original_form_candidate,
)
from src.modules.application_package_generator.source_bound_fill import (
    ReviewedTemplateMap,
    _utc,
)

from .application_review import _access
from .models import OriginalFormReviewCandidate as Candidate
from .models import OriginalFormReviewReceipt as Receipt
from .models import SaasMember, SaasTenant
from .service import audit, now_utc, recheck_tenant_principal

MAX_CANDIDATES = 20
SHA = r'^[a-f0-9]{64}$'
BINDING = ('schema', 'source', 'map_sha256', 'identity_fields_sha256', 'output_sha256')
FALSE_FLAGS = ('current_revision_attested', 'mapping_exhaustive', 'independent_human_review',
               'official_identity_verified', 'application_ready', 'external_export_allowed', 'submitted')
REVIEW_ERRORS = (ValueError, KeyError, TypeError, OSError, XMLSyntaxError, zipfile.BadZipFile)


class CandidateInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reviewer_id: str = Field(min_length=1, max_length=36)
    item_code: Literal['application_form', 'goods_description']
    file_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    mapping: ReviewedTemplateMap
    signatory: Literal['UNKNOWN', 'DIRECTOR', 'REPRESENTATIVE', 'DELEGATED_SIGNER'] = 'UNKNOWN'
    goods_used: StrictBool | None = None


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    candidate_sha256: str = Field(pattern=SHA)
    document_sha256: str = Field(pattern=SHA)
    confirm_exact_private_form: StrictBool


def _member(session, tenant, member_id):
    return session.scalar(select(SaasMember).where(SaasMember.id == member_id,
        SaasMember.tenant_id == tenant, SaasMember.active.is_(True),
        SaasMember.role.in_(('owner', 'admin'))))


def _participants(session, p):
    if (p.creator_id == p.reviewer_id or not _member(session, p.tenant_id, p.creator_id)
            or not _member(session, p.tenant_id, p.reviewer_id)):
        raise HTTPException(409, 'Assigned review participants are no longer eligible')


def _lock(session, principal):
    session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == principal.tenant_id).with_for_update())


def _build(session, principal, run_id, payload, now):
    return build_original_form_candidate(session, customer_id=principal.customer_id, run_id=run_id,
        item_code=payload.item_code, file_id=payload.file_id, mapping=payload.mapping,
        signatory=payload.signatory, goods_used=payload.goods_used, now=now)


def _validate(raw, receipt, principal, run_id, payload):
    source = receipt['source']
    if (not 0 < len(raw) <= MAX_BYTES or hashlib.sha256(raw).hexdigest() != receipt['output_sha256']
            or digest({k:receipt[k] for k in BINDING}) != receipt['candidate_sha256']
            or receipt['schema'] != 'archived-original-form-candidate-v1'
            or receipt['status'] != 'PRIVATE_FORM_CANDIDATE_ONLY'
            or any(receipt.get(k) is not False for k in FALSE_FLAGS)
            or (source['customer_id'], source['run_id'], source['item_code'], source['file_id']) !=
               (principal.customer_id, run_id, payload.item_code, payload.file_id)
            or source['template_sha256'] != payload.mapping.template_sha256
            or receipt['map_sha256'] != digest(payload.mapping.model_dump(mode='json'))):
        raise ValueError('Candidate scope or integrity mismatch')


def _stored(p, principal):
    payload = CandidateInput.model_validate(p.input_json)
    _validate(p.document_bytes, p.receipt_json, principal, p.run_id, payload)
    if (p.reviewer_id != payload.reviewer_id or p.document_sha256 != p.receipt_json['output_sha256']
            or p.candidate_sha256 != p.receipt_json['candidate_sha256']):
        raise ValueError('Stored candidate integrity mismatch')
    return payload


def _receipt(session, p):
    return session.scalar(select(Receipt).where(Receipt.candidate_id == p.id))


def _view(p, d=None):
    source = p.receipt_json['source']
    return {'candidate_id':p.id, 'run_id':p.run_id, 'creator_id':p.creator_id, 'reviewer_id':p.reviewer_id,
            'source':{k:source.get(k) for k in ('procurement_ref','item_code','file_id','observed_version',
                'template_sha256','archive_sha256','notice_xml_sha256','requirement_sha256','plan_sha256')},
            'map_sha256':p.receipt_json['map_sha256'], 'identity_fields_sha256':p.receipt_json['identity_fields_sha256'],
            'candidate_sha256':p.candidate_sha256, 'document_sha256':p.document_sha256,
            'created_at':_utc(p.created_at).isoformat(), 'expires_at':_utc(p.expires_at).isoformat(),
            'status':'INDEPENDENT_INTERNAL_REVIEW_RECORDED' if d else 'PRIVATE_FORM_REVIEW_PENDING',
            'receipt_id':d.id if d else None, 'reviewed_at':_utc(d.created_at).isoformat() if d else None,
            'historical_only':True, 'application_ready':False, 'external_export_allowed':False,
            'signed':False, 'submitted':False}


def _owned(session, principal, run_id, candidate_id):
    _access(session, principal, run_id)
    p = session.scalar(select(Candidate).where(Candidate.id == candidate_id,
        Candidate.tenant_id == principal.tenant_id, Candidate.run_id == run_id,
        or_(Candidate.creator_id == principal.member_id, Candidate.reviewer_id == principal.member_id)))
    if not p:
        raise HTTPException(404, 'Private form candidate not found')
    return p


def create(session, principal, run_id, payload):
    _access(session, principal, run_id)
    if payload.reviewer_id == principal.member_id or not _member(session, principal.tenant_id, payload.reviewer_id):
        raise HTTPException(422, 'Distinct eligible tenant reviewer required')
    _lock(session, principal)
    if session.scalar(select(func.count(Candidate.id)).where(Candidate.tenant_id == principal.tenant_id)) >= MAX_CANDIDATES:
        raise HTTPException(429, 'Private form history limit reached')
    now = now_utc()
    try:
        raw, receipt = _build(session, principal, run_id, payload, now)
        _validate(raw, receipt, principal, run_id, payload)
    except REVIEW_ERRORS as exc:
        raise HTTPException(422, 'Private original form candidate unavailable') from exc
    recheck_tenant_principal(session, principal)
    _access(session, principal, run_id)
    p = Candidate(tenant_id=principal.tenant_id, run_id=run_id, creator_id=principal.member_id,
        reviewer_id=payload.reviewer_id, input_json=payload.model_dump(mode='json'), receipt_json=receipt,
        document_bytes=raw, document_sha256=receipt['output_sha256'], candidate_sha256=receipt['candidate_sha256'],
        created_at=now, expires_at=now+timedelta(minutes=30))
    _participants(session, p)
    if _utc(p.expires_at) <= now_utc():
        raise HTTPException(409, 'Candidate expired during creation')
    session.add(p); session.flush()
    audit(session, principal.tenant_id, 'original_form_candidate', principal.member_id, detail=p.id)
    session.commit()
    return _view(p)


def history(session, principal, run_id):
    _access(session, principal, run_id)
    rows = session.scalars(select(Candidate).where(Candidate.tenant_id == principal.tenant_id,
        Candidate.run_id == run_id, or_(Candidate.creator_id == principal.member_id,
        Candidate.reviewer_id == principal.member_id)).order_by(Candidate.created_at.desc()).limit(MAX_CANDIDATES))
    return {'items':[_view(p, _receipt(session, p)) for p in rows], 'historical_only':True,
            'application_ready':False, 'external_export_allowed':False}


def download(session, principal, run_id, candidate_id):
    p = _owned(session, principal, run_id, candidate_id)
    _participants(session, p)
    if _utc(p.expires_at) <= now_utc():
        raise HTTPException(409, 'Private form candidate expired')
    try:
        _stored(p, principal)
    except REVIEW_ERRORS as exc:
        raise HTTPException(409, 'Stored candidate integrity mismatch') from exc
    return p.document_bytes


def acknowledge(session, principal, run_id, candidate_id, payload):
    p = _owned(session, principal, run_id, candidate_id)
    if p.reviewer_id != principal.member_id or p.creator_id == principal.member_id:
        raise HTTPException(403, 'Assigned independent reviewer required')
    if (not payload.confirm_exact_private_form or payload.candidate_sha256 != p.candidate_sha256
            or payload.document_sha256 != p.document_sha256):
        raise HTTPException(409, 'Exact private form review required')
    _lock(session, principal)
    _participants(session, p)
    now = now_utc()
    if _utc(p.expires_at) <= now:
        raise HTTPException(409, 'Private form candidate expired')
    try:
        original = _stored(p, principal)
        raw, current = _build(session, principal, run_id, original, now)
        _validate(raw, current, principal, run_id, original)
        # ZIP timestamps can vary; compare every inner member and all evidence
        # bindings, retaining the hash of the actual reviewed document.
        if (any(current[k] != p.receipt_json[k] for k in BINDING if k != 'output_sha256')
                or _parts(raw) != _parts(p.document_bytes)):
            raise ValueError('Current candidate differs')
    except REVIEW_ERRORS as exc:
        raise HTTPException(409, 'Source, identity or exact document changed') from exc
    recheck_tenant_principal(session, principal)
    _access(session, principal, run_id)
    _participants(session, p)
    if _utc(p.expires_at) <= now_utc():
        raise HTTPException(409, 'Private form candidate expired')
    d = _receipt(session, p)
    if d:
        if (d.reviewer_id, d.candidate_sha256, d.document_sha256) != (p.reviewer_id, p.candidate_sha256, p.document_sha256):
            raise HTTPException(409, 'Stored review scope mismatch')
        return _view(p, d)
    d = Receipt(candidate_id=p.id, reviewer_id=principal.member_id, candidate_sha256=p.candidate_sha256,
                document_sha256=p.document_sha256, created_at=now_utc())
    try:
        session.add(d); session.flush()
        audit(session, principal.tenant_id, 'original_form_review_recorded', principal.member_id, detail=d.id)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, 'Concurrent review; reload history') from exc
    return _view(p, d)
