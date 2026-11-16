"""User-supplied copies for recorded actual costs, never payment verification."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import func, select

from src.modules.saas_foundation import company_actual_costs as actual
from src.modules.saas_foundation import company_portfolio as portfolio
from src.modules.saas_foundation import company_readiness as readiness
from src.modules.saas_foundation.commercial_attachment_bytes import inspect_attachment
from src.modules.saas_foundation.company_cost_evidence import FORMATS
from src.modules.saas_foundation.models import (
    CompanyActualCostEvidence,
    CompanyActualCostSnapshot,
    CompanyPriceScenario,
    SaasMember,
)
from src.modules.saas_foundation.service import audit, role_required

RowKind = Literal['PLANNED','UNPLANNED']
DocumentKind = Literal['INVOICE','CONTRACT','TIMESHEET','ACCEPTANCE_ACT','PAYMENT_RECORD','OTHER']
DOCUMENT_KINDS = {'INVOICE','CONTRACT','TIMESHEET','ACCEPTANCE_ACT','PAYMENT_RECORD','OTHER'}
MAX_DOCUMENTS_PER_TENANT = 100


def target(session,principal,case_id,scenario_id,snapshot_id,row_kind,ordinal):
    baseline,estimate,baseline_digest=actual._baseline(session,principal,case_id,scenario_id)
    snapshot=session.scalar(actual._query(baseline).where(CompanyActualCostSnapshot.id==snapshot_id).execution_options(populate_existing=True))
    if snapshot is None:
        raise HTTPException(404,'Actual snapshot not found')
    view=actual._view(principal,baseline,estimate,baseline_digest,snapshot)
    if row_kind not in ('PLANNED','UNPLANNED'):
        raise HTTPException(422,'Unknown actual row kind')
    rows=view['result']['lines' if row_kind=='PLANNED' else 'unplanned_costs']
    if not 1<=ordinal<=len(rows):
        raise HTTPException(404,'Actual row not found')
    line=rows[ordinal-1]
    if row_kind=='PLANNED' and line['status']!='USER_REPORTED_ACTUAL':
        raise HTTPException(409,'Actual observation required before attaching evidence')
    canonical=json.dumps({'scenario_id':baseline.id,'scenario_revision':baseline.revision,'baseline_sha256':baseline_digest,'snapshot_id':snapshot.id,'snapshot_revision':snapshot.revision,'as_of':view['inputs']['as_of'],'row_kind':row_kind,'line':line},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    return {**actual._scope(principal,baseline,baseline_digest),'snapshot_id':snapshot.id,'snapshot_revision':snapshot.revision,'as_of':view['inputs']['as_of'],'row_kind':row_kind,'line_ordinal':ordinal,'line_title':line['title'],'actual_amount_rub':line['actual_amount_rub'],'line_sha256':hashlib.sha256(canonical).hexdigest()}


def _existing(session,scope):
    return session.scalar(select(CompanyActualCostEvidence).where(CompanyActualCostEvidence.snapshot_id==scope['snapshot_id'],CompanyActualCostEvidence.row_kind==scope['row_kind'],CompanyActualCostEvidence.line_ordinal==scope['line_ordinal']).execution_options(populate_existing=True))


def _check(row,scope):
    if row.snapshot_id!=scope['snapshot_id'] or row.row_kind!=scope['row_kind'] or row.line_ordinal!=scope['line_ordinal'] or row.line_sha256!=scope['line_sha256'] or row.document_kind not in DOCUMENT_KINDS or row.format_hint not in FORMATS:
        raise HTTPException(409,'Stored actual evidence binding mismatch')
    try:
        inspection=inspect_attachment(row.raw_bytes,row.format_hint)
    except ValueError as exc:
        raise HTTPException(409,'Stored actual evidence format mismatch') from exc
    if inspection!=row.inspection_json:
        raise HTTPException(409,'Stored actual evidence integrity mismatch')
    return inspection


def _view(scope,row,inspection):
    return {**scope,'evidence_id':row.id,'member_id':row.member_id,'document_kind':row.document_kind,'format_hint':row.format_hint,'created_at':portfolio._utc(row.created_at),'inspection':{k:v for k,v in inspection.items() if k!='text_preview'},'origin':'USER_SUPPLIED_UNATTESTED','stored_bytes_reverified':True,'document_origin_verified':False,'actual_amount_verified':False,'payment_verified':False,'contract_execution_verified':False}


def save(session,principal,case_id,scenario_id,snapshot_id,row_kind,ordinal,raw,format_hint,document_kind,line_sha256):
    role_required(principal,'owner','admin')
    scope=target(session,principal,case_id,scenario_id,snapshot_id,row_kind,ordinal)
    if scope['line_sha256']!=line_sha256:raise HTTPException(409,'Actual row binding changed; refresh')
    if document_kind not in DOCUMENT_KINDS or format_hint not in FORMATS:raise HTTPException(422,'Unsupported actual evidence type')
    try:inspection=inspect_attachment(raw,format_hint)
    except ValueError as exc:raise HTTPException(422,'Invalid or unsupported actual evidence bytes') from exc
    portfolio._owned_case(session,principal,case_id,lock=True)
    readiness.lock_tenant(session,principal)
    member=session.get(SaasMember,principal.member_id,populate_existing=True)
    if not member or member.role not in {'owner','admin'}:raise HTTPException(403,'Current manager permission required')
    scope=target(session,principal,case_id,scenario_id,snapshot_id,row_kind,ordinal)
    if scope['line_sha256']!=line_sha256:raise HTTPException(409,'Actual row binding changed; refresh')
    row=_existing(session,scope)
    if row:
        previous=_check(row,scope)
        if row.raw_bytes!=raw or row.format_hint!=format_hint or row.document_kind!=document_kind or row.member_id!=principal.member_id:raise HTTPException(409,'Different document already attached to immutable actual row')
        return _view(scope,row,previous)
    count=session.scalar(select(func.count()).select_from(CompanyActualCostEvidence).join(CompanyActualCostSnapshot,CompanyActualCostSnapshot.id==CompanyActualCostEvidence.snapshot_id).join(CompanyPriceScenario,CompanyPriceScenario.id==CompanyActualCostSnapshot.scenario_id).where(CompanyPriceScenario.tenant_id==principal.tenant_id))
    if count>=MAX_DOCUMENTS_PER_TENANT:raise HTTPException(429,'Actual evidence budget reached')
    row=CompanyActualCostEvidence(snapshot_id=snapshot_id,row_kind=row_kind,line_ordinal=ordinal,line_sha256=line_sha256,member_id=principal.member_id,document_kind=document_kind,format_hint=format_hint,raw_bytes=raw,inspection_json=inspection)
    session.add(row);session.flush();audit(session,principal.tenant_id,'company_actual_evidence_saved',principal.member_id,detail=row.id);session.commit()
    return _view(scope,row,inspection)


def read(session,principal,case_id,scenario_id,snapshot_id,row_kind,ordinal):
    scope=target(session,principal,case_id,scenario_id,snapshot_id,row_kind,ordinal);row=_existing(session,scope)
    return {**scope,'evidence':_view(scope,row,_check(row,scope)) if row else None}


def download(session,principal,case_id,scenario_id,snapshot_id,row_kind,ordinal):
    scope=target(session,principal,case_id,scenario_id,snapshot_id,row_kind,ordinal);row=_existing(session,scope)
    if row is None:raise HTTPException(404,'Actual evidence not found')
    inspection=_check(row,scope)
    return bytes(row.raw_bytes),row.format_hint,inspection['sha256']
