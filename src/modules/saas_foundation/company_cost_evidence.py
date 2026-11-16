"""User-supplied cost documents, scoped to immutable PRICE-01 estimate lines."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import func, select

from src.modules.saas_foundation import company_portfolio as portfolio
from src.modules.saas_foundation import company_price_scenarios as price
from src.modules.saas_foundation import company_readiness as readiness
from src.modules.saas_foundation.commercial_attachment_bytes import inspect_attachment
from src.modules.saas_foundation.commercial_capture import _authorized
from src.modules.saas_foundation.models import (
    CompanyCostEvidence,
    CompanyPriceScenario,
    SaasMember,
)
from src.modules.saas_foundation.service import audit, role_required

DocumentKind = Literal['QUOTE','INVOICE','CONTRACT','TIMESHEET','OTHER']
FormatHint = Literal['pdf','docx','xlsx']
DOCUMENT_KINDS = {'QUOTE','INVOICE','CONTRACT','TIMESHEET','OTHER'}
FORMATS = {'pdf','docx','xlsx'}
MAX_DOCUMENTS_PER_TENANT = 100


def _line(session,principal,case_id,scenario_id,ordinal):
    _authorized(session,principal)
    portfolio._owned_case(session,principal,case_id)
    scenario=session.scalar(price._query(principal,case_id).where(CompanyPriceScenario.id==scenario_id).execution_options(populate_existing=True))
    if scenario is None:
        raise HTTPException(404,'Saved scenario not found')
    view=price._view(principal,scenario)
    estimate=view.get('itemized_estimate')
    if estimate is None:
        raise HTTPException(409,'Saved itemized scenario required')
    if not 1<=ordinal<=len(estimate['lines']):
        raise HTTPException(404,'Estimate line not found')
    line=estimate['lines'][ordinal-1]
    # Bind separately to scenario identity/revision, not just to the row text.
    canonical=json.dumps({'scenario_id':scenario.id,'revision':scenario.revision,'line':line},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    return scenario,line,hashlib.sha256(canonical).hexdigest()


def _existing(session,scenario,ordinal):
    return session.scalar(select(CompanyCostEvidence).where(CompanyCostEvidence.scenario_id==scenario.id,CompanyCostEvidence.line_ordinal==ordinal).execution_options(populate_existing=True))


def _check(row,scenario,line,digest):
    if (row.scenario_id!=scenario.id or row.line_ordinal!=line['ordinal'] or row.line_sha256!=digest
            or row.document_kind not in DOCUMENT_KINDS or row.format_hint not in FORMATS):
        raise HTTPException(409,'Stored cost document binding mismatch')
    try:
        inspection=inspect_attachment(row.raw_bytes,row.format_hint)
    except ValueError as exc:
        raise HTTPException(409,'Stored cost document format mismatch') from exc
    if inspection!=row.inspection_json:
        raise HTTPException(409,'Stored cost document integrity mismatch')
    return inspection


def _view(principal,scenario,line,row,inspection):
    return {'customer_id':principal.customer_id,'case_id':scenario.case_id,'scenario_id':scenario.id,'scenario_revision':scenario.revision,
            'line_ordinal':line['ordinal'],'line_sha256':row.line_sha256,'line_title':line['title'],'line_amount_rub':line['amount_rub'],
            'evidence_id':row.id,'member_id':row.member_id,'document_kind':row.document_kind,'format_hint':row.format_hint,
            'created_at':portfolio._utc(row.created_at),'inspection':{k:v for k,v in inspection.items() if k!='text_preview'},
            'origin':'USER_SUPPLIED_UNATTESTED','stored_bytes_reverified':True,'document_origin_verified':False,
            'cost_amount_verified':False,'payment_verified':False,'external_submission_allowed':False}


def save(session,principal,case_id,scenario_id,ordinal,raw,format_hint,document_kind,line_sha256):
    role_required(principal,'owner','admin')
    scenario,line,digest=_line(session,principal,case_id,scenario_id,ordinal)
    if line_sha256!=digest:
        raise HTTPException(409,'Estimate line binding changed; refresh')
    if document_kind not in DOCUMENT_KINDS or format_hint not in FORMATS:
        raise HTTPException(422,'Unsupported cost document type')
    try:
        inspection=inspect_attachment(raw,format_hint)
    except ValueError as exc:
        raise HTTPException(422,'Invalid or unsupported cost document bytes') from exc
    portfolio._owned_case(session,principal,case_id,lock=True)
    readiness.lock_tenant(session,principal)
    member=session.get(SaasMember,principal.member_id,populate_existing=True)
    if not member or member.role not in {'owner','admin'}:
        raise HTTPException(403,'Current manager permission required')
    scenario,line,digest=_line(session,principal,case_id,scenario_id,ordinal)
    if line_sha256!=digest:
        raise HTTPException(409,'Estimate line binding changed; refresh')
    row=_existing(session,scenario,ordinal)
    if row:
        previous=_check(row,scenario,line,digest)
        if row.raw_bytes!=raw or row.format_hint!=format_hint or row.document_kind!=document_kind or row.member_id!=principal.member_id:
            raise HTTPException(409,'Different document already attached to immutable estimate line')
        return _view(principal,scenario,line,row,previous)
    count=session.scalar(select(func.count()).select_from(CompanyCostEvidence).join(CompanyPriceScenario,CompanyPriceScenario.id==CompanyCostEvidence.scenario_id).where(CompanyPriceScenario.tenant_id==principal.tenant_id))
    if count>=MAX_DOCUMENTS_PER_TENANT:
        raise HTTPException(429,'Cost evidence budget reached')
    row=CompanyCostEvidence(scenario_id=scenario.id,line_ordinal=ordinal,line_sha256=digest,member_id=principal.member_id,document_kind=document_kind,format_hint=format_hint,raw_bytes=raw,inspection_json=inspection)
    session.add(row);session.flush();audit(session,principal.tenant_id,'company_cost_evidence_saved',principal.member_id,detail=row.id);session.commit()
    return _view(principal,scenario,line,row,inspection)


def read(session,principal,case_id,scenario_id,ordinal):
    scenario,line,digest=_line(session,principal,case_id,scenario_id,ordinal)
    row=_existing(session,scenario,ordinal)
    # Return the immutable line binding even if no evidence exists yet, for explicit upload.
    return {'customer_id':principal.customer_id,'case_id':scenario.case_id,'scenario_id':scenario.id,'scenario_revision':scenario.revision,
            'line_ordinal':ordinal,'line_sha256':digest,'line_title':line['title'],'line_amount_rub':line['amount_rub'],
            'evidence':_view(principal,scenario,line,row,_check(row,scenario,line,digest)) if row else None,'external_submission_allowed':False}


def download(session,principal,case_id,scenario_id,ordinal):
    scenario,line,digest=_line(session,principal,case_id,scenario_id,ordinal)
    row=_existing(session,scenario,ordinal)
    if row is None:
        raise HTTPException(404,'Cost evidence not found')
    inspection=_check(row,scenario,line,digest)
    return bytes(row.raw_bytes),row.format_hint,inspection['sha256']
