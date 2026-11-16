"""Cumulative, explicitly user-reported cost snapshots against a saved baseline.

Not a transaction ledger, financial accounting or proof of contract execution.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, localcontext
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from src.modules.saas_foundation import company_portfolio as portfolio
from src.modules.saas_foundation import company_price_scenarios as price
from src.modules.saas_foundation.commercial_capture import _authorized
from src.modules.saas_foundation.models import (
    CompanyActualCostSnapshot,
    CompanyPriceScenario,
    SaasMember,
)
from src.modules.saas_foundation.service import audit, role_required

Digest = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]


class ActualLine(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    ordinal: int = Field(ge=1, le=60, strict=True)
    quantity: price.Quantity
    rate_rub: price.Money
    source_note: str = Field(min_length=1, max_length=500)

    @model_validator(mode='after')
    def zero_quantity(self):
        if Decimal(self.quantity)==0 and Decimal(self.rate_rub)!=0:
            raise ValueError('Explicit zero quantity requires zero rate')
        return self


class SnapshotInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    baseline_sha256: Digest
    as_of: date
    observations: list[ActualLine] = Field(max_length=60)
    unplanned_costs: list[price.CostLine] = Field(max_length=30)
    note: str = Field(min_length=1, max_length=2000)
    confirm_cumulative_user_report: Literal[True]
    confirm_no_double_count: Literal[True]

    @model_validator(mode='after')
    def validate_observations(self):
        if not self.observations and not self.unplanned_costs:
            raise ValueError('At least one observation or unplanned expense required')
        if len({x.ordinal for x in self.observations})!=len(self.observations):
            raise ValueError('Duplicate baseline line observation')
        keys=set()
        for x in self.unplanned_costs:
            if x.source_kind!='USER_REPORTED_ACTUAL':raise ValueError('Unplanned cost must be reported actual')
            key=(x.category,x.title.casefold(),x.unit.casefold(),Decimal(x.quantity),Decimal(x.rate_rub),x.source_note.casefold())
            if key in keys:raise ValueError('Duplicate unplanned expense')
            keys.add(key)
        return self


class SaveInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=0,le=30,strict=True)
    idempotency_key: str = Field(min_length=8,max_length=128)
    snapshot: SnapshotInput


def _baseline(session,principal,case_id,scenario_id):
    _authorized(session,principal);portfolio._owned_case(session,principal,case_id)
    row=session.scalar(price._query(principal,case_id).where(CompanyPriceScenario.id==scenario_id).execution_options(populate_existing=True))
    if row is None:raise HTTPException(404,'Saved scenario not found')
    estimate=price._view(principal,row).get('itemized_estimate')
    if estimate is None:raise HTTPException(409,'Saved itemized baseline required')
    canonical=json.dumps({'scenario_id':row.id,'revision':row.revision,'estimate':estimate},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    return row,estimate,hashlib.sha256(canonical).hexdigest()


def calculate(estimate,digest,payload):
    if payload.baseline_sha256!=digest:raise ValueError('Baseline digest mismatch')
    with localcontext() as ctx:
        ctx.prec=40
        def amount(quantity,rate):return (Decimal(quantity)*Decimal(rate)).quantize(price.CENT,rounding=ROUND_CEILING)
        def money(x):return str(x.quantize(price.CENT))
        def delta_pct(delta,base):return str((delta/base*100).quantize(Decimal('0.0001'),rounding=ROUND_HALF_UP)) if base else None
        observations={x.ordinal:x for x in payload.observations}
        if any(not 1<=k<=len(estimate['lines']) for k in observations):raise ValueError('Unknown baseline ordinal')
        totals={k:{'plan':Decimal(0),'matched_plan':Decimal(0),'observed':Decimal(0),'unplanned':Decimal(0),'missing':0} for k in price.COST_FIELDS}
        rows=[]
        for line in estimate['lines']:
            plan=Decimal(line['amount_rub']); t=totals[line['category']]; t['plan']+=plan
            observed=observations.get(line['ordinal'])
            row={'ordinal':line['ordinal'],'title':line['title'],'category':line['category'],'unit':line['unit'],'planned_quantity':line['quantity'],'planned_rate_rub':line['rate_rub'],'planned_amount_rub':line['amount_rub']}
            if observed is None:
                t['missing']+=1;row.update(status='NOT_REPORTED',actual_quantity=None,actual_rate_rub=None,actual_amount_rub=None,variance_rub=None,variance_percent=None,source_note=None)
            else:
                actual=amount(observed.quantity,observed.rate_rub);t['matched_plan']+=plan;t['observed']+=actual
                row.update(status='USER_REPORTED_ACTUAL',actual_quantity=observed.quantity,actual_rate_rub=observed.rate_rub,actual_amount_rub=money(actual),variance_rub=money(actual-plan),variance_percent=delta_pct(actual-plan,plan),source_note=observed.source_note)
            rows.append(row)
        extra=[]
        for i,line in enumerate(payload.unplanned_costs,1):
            actual=amount(line.quantity,line.rate_rub);totals[line.category]['unplanned']+=actual
            extra.append({'ordinal':i,**line.model_dump(mode='json'),'actual_amount_rub':money(actual)})
        if any(t['observed']+t['unplanned']>Decimal('999999999999.99') for t in totals.values()):raise ValueError('Actual category total exceeds money limit')
        def summary(t):
            observed=t['observed']+t['unplanned'];matched=t['observed']-t['matched_plan']
            return {'planned_rub':money(t['plan']),'matched_planned_rub':money(t['matched_plan']),'reported_planned_line_actual_rub':money(t['observed']),'reported_unplanned_rub':money(t['unplanned']),'reported_total_rub':money(observed),'missing_planned_lines':t['missing'],'matched_variance_rub':money(matched) if t['matched_plan'] else None,'matched_variance_percent':delta_pct(matched,t['matched_plan']),'all_planned_lines_reported':t['missing']==0,'reported_vs_full_plan_rub':money(observed-t['plan']) if t['missing']==0 else None}
        overall={k:sum(t[k] for t in totals.values()) for k in next(iter(totals.values()))}
        return {'schema':'company_actual_cost_snapshot_v1','currency':'RUB','baseline_sha256':digest,'as_of':payload.as_of.isoformat(),'lines':rows,'unplanned_costs':extra,'category_totals':{k:summary(t) for k,t in totals.items()},'totals':summary(overall),'rounding_policy':'CEIL_EACH_LINE_TO_KOPECKS_THEN_SUM','basis':'CUMULATIVE_USER_REPORTED_COSTS_BEFORE_REVENUE_RATES','origin':'USER_REPORTED_UNVERIFIED','payment_verified':False,'actual_amounts_independently_verified':False,'contract_cost_coverage_complete':False,'contract_execution_verified':False,'revenue_or_profit_verified':False,'external_submission_allowed':False}


def _result(estimate,digest,payload):
    if payload.baseline_sha256!=digest:raise HTTPException(409,'Baseline changed; refresh')
    if payload.as_of>datetime.now(UTC).date():raise HTTPException(422,'Future actual cost date not allowed')
    try:return calculate(estimate,digest,payload)
    except (ValueError,ArithmeticError) as exc:raise HTTPException(422,str(exc)) from exc


def _query(row):
    return select(CompanyActualCostSnapshot).where(CompanyActualCostSnapshot.scenario_id==row.id)


def _scope(principal,row,digest):
    return {'customer_id':principal.customer_id,'case_id':row.case_id,'scenario_id':row.id,'scenario_revision':row.revision,'baseline_sha256':digest,'external_submission_allowed':False}


def _view(principal,baseline,estimate,digest,row):
    try:
        payload=SnapshotInput.model_validate(row.input_json)
        result=calculate(estimate,digest,payload)
        if result!=row.result_json or payload.model_dump(mode='json')!=row.input_json:raise ValueError('Stored actual snapshot mismatch')
    except (ValueError,ArithmeticError,TypeError,KeyError) as exc:raise HTTPException(409,'Stored actual snapshot integrity mismatch') from exc
    return {**_scope(principal,baseline,digest),'snapshot_id':row.id,'revision':row.revision,'member_id':row.member_id,'created_at':portfolio._utc(row.created_at),'inputs':row.input_json,'result':result}


def preview(session,principal,case_id,scenario_id,payload):
    baseline,estimate,digest=_baseline(session,principal,case_id,scenario_id)
    return {**_scope(principal,baseline,digest),'inputs_stored':False,'result':_result(estimate,digest,payload)}


def history(session,principal,case_id,scenario_id,offset,limit):
    baseline,estimate,digest=_baseline(session,principal,case_id,scenario_id)
    query=_query(baseline).order_by(CompanyActualCostSnapshot.revision.desc())
    rows=list(session.scalars(query.offset(offset).limit(limit+1)))
    return {**_scope(principal,baseline,digest),'planned_lines':estimate['lines'],'items':[_view(principal,baseline,estimate,digest,row) for row in rows[:limit]],'has_more':len(rows)>limit}


def save(session,principal,case_id,scenario_id,payload):
    role_required(principal,'owner','admin')
    portfolio._owned_case(session,principal,case_id,lock=True)
    baseline,estimate,digest=_baseline(session,principal,case_id,scenario_id)
    member=session.get(SaasMember,principal.member_id,populate_existing=True)
    if not member or member.role not in {'owner','admin'}:raise HTTPException(403,'Current manager permission required')
    body=payload.snapshot.model_dump(mode='json');query=_query(baseline)
    prior=session.scalar(query.where(CompanyActualCostSnapshot.idempotency_key==payload.idempotency_key))
    if prior:
        if prior.member_id!=principal.member_id or prior.input_json!=body or prior.revision!=payload.expected_revision+1:raise HTTPException(409,'Conflicting actual snapshot replay')
        return _view(principal,baseline,estimate,digest,prior)
    latest=session.scalar(query.order_by(CompanyActualCostSnapshot.revision.desc()).limit(1))
    revision=latest.revision if latest else 0
    if revision!=payload.expected_revision:raise HTTPException(409,'Actual snapshot revision changed; refresh')
    if revision>=30:raise HTTPException(429,'Actual snapshot revision limit reached')
    if latest:
        previous=_view(principal,baseline,estimate,digest,latest)
        if payload.snapshot.as_of.isoformat()<previous['inputs']['as_of']:raise HTTPException(409,'Actual snapshot date precedes latest report')
    result=_result(estimate,digest,payload.snapshot)
    row=CompanyActualCostSnapshot(scenario_id=baseline.id,member_id=principal.member_id,revision=revision+1,idempotency_key=payload.idempotency_key,input_json=body,result_json=result)
    session.add(row);session.flush();audit(session,principal.tenant_id,'company_actual_cost_snapshot_saved',principal.member_id,detail=row.id);session.commit()
    return _view(principal,baseline,estimate,digest,row)
