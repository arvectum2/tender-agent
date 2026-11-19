"""Feature-gated, authenticated acknowledgement of an exact private draft ZIP."""
from __future__ import annotations

import base64
import binascii
import zipfile
from datetime import timedelta
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.modules.application_package_generator.checklist_bundle_gate import (
    bundle_inputs_digest,
    preview_plan,
)
from src.modules.application_package_generator.customer_draft_export import (
    build_customer_draft_export,
)
from src.modules.application_package_generator.evidence_approval_gate import (
    _verify_receipts,
    build_with_evidence_approval,
    preview_evidence_approval,
)
from src.modules.application_package_generator.private_review_bundle import (
    verify_private_review_bundle,
)
from src.modules.application_package_generator.reviewed_commercial_drafts import (
    DeclarationTerms,
    OfferTerms,
)
from src.modules.application_package_generator.source_bound_fill import (
    ReviewedTemplateMap,
    _utc,
)
from src.modules.saas_foundation.models import (
    ApplicationReviewDecision as Decision,
)
from src.modules.saas_foundation.models import (
    ApplicationReviewPreview as Preview,
)
from src.modules.saas_foundation.models import (
    SaasTenant,
)
from src.modules.saas_foundation.service import (
    audit,
    legal_required,
    now_utc,
    owned_run,
    recheck_tenant_principal,
    role_required,
)
from src.modules.tender_operator_agent_demo.operator_cost_scenarios import (
    ExplicitCostScenarioRequest,
)

MAX_REQUEST_BYTES=1024*1024
MAX_ARCHIVE_BYTES=2*1024*1024
MAX_PREVIEWS_PER_TENANT=20
SHA=r'^[0-9a-f]{64}$'


class TemplateInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    base64_bytes: str=Field(min_length=1,max_length=700000)
    mapping: ReviewedTemplateMap


class PreviewInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    signatory: Literal['UNKNOWN','DIRECTOR','REPRESENTATIVE','DELEGATED_SIGNER']='UNKNOWN'
    goods_used: StrictBool|None=None
    templates: dict[str,TemplateInput]=Field(default_factory=dict,max_length=2)
    selections: dict[str,str]=Field(default_factory=dict,max_length=8)
    cost: ExplicitCostScenarioRequest|None=None
    offer_terms: OfferTerms|None=None
    declaration_terms: DeclarationTerms|None=None


class ConfirmInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    archive_sha256: str=Field(pattern=SHA)
    confirm_reviewed_private_archive: StrictBool


def _access(session,principal,run_id):
    role_required(principal,'owner','admin')
    legal_required(session,principal)
    owned_run(session,principal,run_id)


def _args(session,principal,root,run_id,payload,now):
    _access(session,principal,run_id)
    try:
        templates={k:(base64.b64decode(t.base64_bytes,validate=True),t.mapping) for k,t in payload.templates.items()}
    except (ValueError,binascii.Error) as exc:
        raise HTTPException(422,'Invalid template encoding') from exc
    if sum(len(raw) for raw,_ in templates.values())>512*1024:
        raise HTTPException(413,'Template limit exceeded')
    p=preview_plan(customer_id=principal.customer_id,run_id=run_id,
                   signatory=payload.signatory,goods_used=payload.goods_used)
    args={'customer_id':principal.customer_id,'root':root,'run_id':run_id,'approved_digest':p['approval_digest'],
          'templates':templates,'selections':payload.selections,'cost':payload.cost,'offer_terms':payload.offer_terms,
          'declaration_terms':payload.declaration_terms,'signatory':payload.signatory,'goods_used':payload.goods_used,'now':now}
    args['approved_inputs_digest']=bundle_inputs_digest(**{k:args[k] for k in
        ('approved_digest','templates','selections','cost','offer_terms','declaration_terms')})
    return args


def _owned(session,principal,run_id,preview_id):
    _access(session,principal,run_id)
    p=session.scalar(select(Preview).where(Preview.id==preview_id,Preview.tenant_id==principal.tenant_id,
        Preview.run_id==run_id,Preview.member_id==principal.member_id))
    if not p:
        raise HTTPException(404,'Private review preview not found')
    return p


def _manifest(p,principal):
    m=verify_private_review_bundle(p.archive_bytes,expected_sha256=p.archive_sha256)
    if m['customer_id']!=principal.customer_id or m['procurement_ref']!=p.procurement_ref or m['plan_review_ref']!='checklist-sha256:'+p.plan_sha256:
        raise ValueError('Private archive scope mismatch')
    return m


def _view(p,d=None,manifest=None):
    result={'preview_id':p.id,'run_id':p.run_id,'procurement_ref':p.procurement_ref,'archive_sha256':p.archive_sha256,
        'plan_sha256':p.plan_sha256,'inputs_sha256':p.inputs_sha256,'evidence_sha256':p.evidence_sha256,
        'created_at':_utc(p.created_at).isoformat(),'expires_at':_utc(p.expires_at).isoformat(),
        'created_by_member_id':p.member_id,'status':'INTERNAL_REVIEW_RECORDED' if d else 'PRIVATE_PREVIEW',
        'decision_id':d.id if d else None,'reviewed_at':_utc(d.created_at).isoformat() if d else None,
        'reviewed_by_member_id':d.member_id if d else None,'historical_not_current_approval':bool(d),
        'application_ready':False,'external_action_allowed':False,'signed':False,'submitted':False}
    if manifest is not None:
        result['open_item_codes']=manifest['unresolved_item_codes']
        result['inventory']=[{k:x[k] for k in ('path','bytes','sha256','role')} for x in manifest['inventory']]
    return result


def create_preview(session,principal,root,run_id,payload):
    _access(session,principal,run_id)
    # Serialize bounded per-tenant writes on PostgreSQL; uniqueness still guards
    # decisions. SQLite is the local synthetic test backend only.
    session.scalar(select(SaasTenant).where(SaasTenant.tenant_id==principal.tenant_id).with_for_update())
    count=session.scalar(select(func.count(Preview.id)).where(Preview.tenant_id==principal.tenant_id))
    if count>=MAX_PREVIEWS_PER_TENANT:
        raise HTTPException(429,'Private review history limit reached')
    now=now_utc()
    try:
        args=_args(session,principal,root,run_id,payload,now)
        snap=preview_evidence_approval(session,**args)
        sha=snap['evidence_approval_digest']
        raw,out=build_with_evidence_approval(session,approved_evidence_digest=sha,**args)
        manifest=out['manifest']
    except (ValueError,ValidationError,KeyError,TypeError) as exc:
        raise HTTPException(422,'Reviewed source or draft inputs unavailable or inconsistent') from exc
    if len(raw)>MAX_ARCHIVE_BYTES:
        raise HTTPException(413,'Private review archive limit exceeded')
    if not any(x['role'] in ('DRAFT_FORM','UNSIGNED_OFFER','UNSIGNED_DECLARATIONS') for x in manifest['inventory']):
        raise HTTPException(422,'At least one reviewable draft is required')
    recheck_tenant_principal(session,principal)
    _access(session,principal,run_id)
    p=Preview(tenant_id=principal.tenant_id,member_id=principal.member_id,run_id=run_id,
        procurement_ref=manifest['procurement_ref'],input_json=payload.model_dump(mode='json'),archive_bytes=raw,
        archive_sha256=out['archive_sha256'],plan_sha256=args['approved_digest'],inputs_sha256=args['approved_inputs_digest'],
        evidence_sha256=sha,created_at=now,expires_at=now+timedelta(minutes=15))
    session.add(p);session.flush()
    audit(session,principal.tenant_id,'application_review_preview',principal.member_id,detail=p.id)
    session.commit()
    return _view(p,manifest=manifest)


def _decision(session,p):
    return session.scalar(select(Decision).where(Decision.preview_id==p.id))


def _checked_manifest(p,principal):
    try:
        return _manifest(p,principal)
    except (ValueError,KeyError,TypeError,EOFError,OSError,zipfile.BadZipFile) as exc:
        raise HTTPException(409,'Stored private review archive is inconsistent') from exc


def download(session,principal,run_id,preview_id):
    p=_owned(session,principal,run_id,preview_id)
    _checked_manifest(p,principal)
    return p.archive_bytes


def history(session,principal,run_id):
    _access(session,principal,run_id)
    rows=session.scalars(select(Preview).where(Preview.tenant_id==principal.tenant_id,
        Preview.run_id==run_id,Preview.member_id==principal.member_id).order_by(Preview.created_at.desc(),Preview.id.desc())
        .limit(MAX_PREVIEWS_PER_TENANT))
    return {'items':[_view(p,_decision(session,p)) for p in rows],'historical_only':True,'application_ready':False}


def confirm(session,principal,root,run_id,preview_id,payload):
    p=_owned(session,principal,run_id,preview_id)
    if not payload.confirm_reviewed_private_archive or payload.archive_sha256!=p.archive_sha256:
        raise HTTPException(409,'Explicit review of the exact archive required')
    manifest=_checked_manifest(p,principal)
    previous=_decision(session,p)
    if previous is not None:
        if (previous.tenant_id!=principal.tenant_id or previous.member_id!=principal.member_id
                or previous.archive_sha256!=p.archive_sha256):
            raise HTTPException(409,'Stored acknowledgement scope mismatch')
        return _view(p,previous)
    now=now_utc()
    if _utc(p.expires_at)<=now:
        raise HTTPException(409,'Private review preview expired; generate again')
    try:
        original=PreviewInput.model_validate(p.input_json)
        args=_args(session,principal,root,run_id,original,now)
        if args['approved_digest']!=p.plan_sha256 or args['approved_inputs_digest']!=p.inputs_sha256:
            raise ValueError('Reviewed inputs changed')
        snap=preview_evidence_approval(session,**args)
        if snap['evidence_approval_digest']!=p.evidence_sha256:
            raise ValueError('Reviewed evidence changed')
        _verify_receipts(manifest,snap['projection'])
    except (ValueError,ValidationError,KeyError,TypeError) as exc:
        raise HTTPException(409,'Source or evidence changed; generate a new preview') from exc
    if _utc(p.expires_at)<=now_utc():
        raise HTTPException(409,'Private review preview expired; generate again')
    recheck_tenant_principal(session,principal)
    _access(session,principal,run_id)
    if _utc(p.expires_at)<=now_utc():
        raise HTTPException(409,'Private review preview expired; generate again')
    d=Decision(preview_id=p.id,tenant_id=principal.tenant_id,member_id=principal.member_id,
               archive_sha256=p.archive_sha256,created_at=now_utc())
    try:
        session.add(d);session.flush()
        audit(session,principal.tenant_id,'application_review_confirmed',principal.member_id,detail=d.id)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409,'Concurrent review; refresh history') from exc
    return _view(p,d)


class CustomerDraftExportInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    archive_sha256: str = Field(pattern=SHA)
    decision_id: str = Field(min_length=1, max_length=64)
    selection: list[Literal['price_offer', 'declarations']] = Field(min_length=1, max_length=2)
    confirm_unsigned_subset: StrictBool


def customer_draft_export(session, principal, root, run_id, preview_id, payload):
    p = _owned(session, principal, run_id, preview_id)
    d = _decision(session, p)
    if (not payload.confirm_unsigned_subset or payload.archive_sha256 != p.archive_sha256
            or not d or d.id != payload.decision_id or d.archive_sha256 != p.archive_sha256
            or d.member_id != principal.member_id or d.tenant_id != principal.tenant_id):
        raise HTTPException(409, 'Exact retained internal acknowledgement required')
    manifest = _checked_manifest(p, principal)
    now = now_utc()
    if _utc(p.expires_at) <= now:
        raise HTTPException(409, 'Private review preview expired; generate again')
    try:
        original = PreviewInput.model_validate(p.input_json)
        args = _args(session, principal, root, run_id, original, now)
        if args['approved_digest'] != p.plan_sha256 or args['approved_inputs_digest'] != p.inputs_sha256:
            raise ValueError('Reviewed inputs changed')
        snap = preview_evidence_approval(session, **args)
        if snap['evidence_approval_digest'] != p.evidence_sha256:
            raise ValueError('Reviewed evidence changed')
        _verify_receipts(manifest, snap['projection'])
        raw = build_customer_draft_export(p.archive_bytes, expected_sha256=p.archive_sha256,
                                         selection=payload.selection)
    except (ValueError, ValidationError, KeyError, TypeError, EOFError, OSError, zipfile.BadZipFile) as exc:
        raise HTTPException(409, 'Selected draft unavailable or evidence changed; review again') from exc
    recheck_tenant_principal(session, principal)
    _access(session, principal, run_id)
    if _utc(p.expires_at) <= now_utc():
        raise HTTPException(409, 'Private review preview expired; generate again')
    return raw
