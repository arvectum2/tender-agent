"""PRICE-01 explicit descriptive samples, not approved corporate norms.

One cumulative actual row per distinct company case. No mixing of quantities or
unit conversions, no inferred completion or accounting attestation. The result
is a preview using immutable snapshots, never an automatic estimate or rate.
"""
from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.modules.saas_foundation import company_actual_costs as actual
from src.modules.saas_foundation import company_actual_evidence as evidence
from src.modules.saas_foundation import company_portfolio as portfolio
from src.modules.saas_foundation.models import CompanyActualCostSnapshot
from src.modules.saas_foundation.service import role_required

Category = Literal['own_labor_rub','external_direct_rub','cash_overhead_rub']
Identifier = Annotated[str,Field(min_length=1,max_length=36)]
MAX_SAMPLES=20


class SampleRef(BaseModel):
    model_config=ConfigDict(extra='forbid')
    case_id: Identifier
    scenario_id: Identifier
    snapshot_id: Identifier
    row_kind: evidence.RowKind
    ordinal: int=Field(ge=1,le=60,strict=True)
    line_sha256: actual.Digest


class PreviewInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    category: Category
    title: str=Field(min_length=1,max_length=160)
    unit: str=Field(min_length=1,max_length=24)
    samples: list[SampleRef]=Field(min_length=1,max_length=MAX_SAMPLES)
    confirm_comparable_reported_rows: Literal[True]
    confirm_one_cumulative_row_per_case: Literal[True]

    @model_validator(mode='after')
    def unique_cases(self):
        if len({x.case_id for x in self.samples})!=len(self.samples):
            raise ValueError('Select only one cumulative row per case')
        return self


def label(value):
    # No synonyms, transliteration, implicit unit conversion or fuzzy matching.
    return ' '.join(value.casefold().split())


def distribution(values,quantum):
    ds=sorted(Decimal(v) for v in values)
    if not ds:raise ValueError('Empty sample')
    with localcontext() as ctx:
        ctx.prec=40
        n=len(ds);median=(ds[(n-1)//2]+ds[n//2])/2
        def format_value(x):return str(x.quantize(quantum,rounding=ROUND_HALF_UP))
        return {'minimum':format_value(ds[0]),'median':format_value(median),'maximum':format_value(ds[-1])}


def _sample(session,principal,ref,payload):
    baseline,estimate,digest=actual._baseline(session,principal,ref.case_id,ref.scenario_id)
    snapshot=session.scalar(actual._query(baseline).order_by(CompanyActualCostSnapshot.revision.desc()).limit(1).execution_options(populate_existing=True))
    if snapshot is None or snapshot.id!=ref.snapshot_id:
        raise HTTPException(409,'Select the latest cumulative snapshot of the specified baseline')
    view=actual._view(principal,baseline,estimate,digest,snapshot)
    rows=view['result']['lines' if ref.row_kind=='PLANNED' else 'unplanned_costs']
    if not 1<=ref.ordinal<=len(rows):raise HTTPException(404,'Actual sample row not found')
    line=rows[ref.ordinal-1]
    if ref.row_kind=='PLANNED':
        if line['status']!='USER_REPORTED_ACTUAL':raise HTTPException(409,'Reported actual row required')
        quantity,rate=line['actual_quantity'],line['actual_rate_rub']
    else:
        if line['source_kind']!='USER_REPORTED_ACTUAL':raise HTTPException(409,'Reported actual row required')
        quantity,rate=line['quantity'],line['rate_rub']
    if line['category']!=payload.category or label(line['title'])!=label(payload.title) or line['unit']!=payload.unit:
        raise HTTPException(422,'Actual row category, title or unit differs; no automatic normalization')
    if Decimal(quantity)<=0:raise HTTPException(422,'Positive reported quantity required for sample')
    canonical=json.dumps({'scenario_id':baseline.id,'scenario_revision':baseline.revision,'baseline_sha256':digest,'snapshot_id':snapshot.id,'snapshot_revision':snapshot.revision,'as_of':view['inputs']['as_of'],'row_kind':ref.row_kind,'line':line},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    if hashlib.sha256(canonical).hexdigest()!=ref.line_sha256:
        raise HTTPException(409,'Actual sample row digest mismatch')
    case=portfolio._view(session,principal,portfolio._owned_case(session,principal,ref.case_id))
    return {'source_platform':case['source_platform'],'external_id':case['external_id'],'case_id':ref.case_id,'scenario_id':baseline.id,'scenario_revision':baseline.revision,
            'baseline_sha256':digest,'snapshot_id':snapshot.id,'snapshot_revision':snapshot.revision,
            'row_kind':ref.row_kind,'ordinal':ref.ordinal,'line_sha256':ref.line_sha256,
            'as_of':view['inputs']['as_of'],'title':line['title'],'unit':line['unit'],
            'reported_quantity':quantity,'reported_rate_rub':rate,'reported_amount_rub':line['actual_amount_rub'],
            'origin':'USER_REPORTED_UNVERIFIED','actual_amount_verified':False}


def preview(session,principal,payload):
    role_required(principal,'owner','admin','analyst')
    rows=[_sample(session,principal,ref,payload) for ref in payload.samples]
    if len({(x['source_platform'],x['external_id']) for x in rows})!=len(rows):raise HTTPException(422,'Duplicate procurement source identity')
    return {'schema':'company_actual_descriptive_sample_v1','customer_id':principal.customer_id,
            'category':payload.category,'title':payload.title,'unit':payload.unit,'currency':'RUB',
            'distinct_case_count':len(rows),'samples':rows,
            'reported_quantity_distribution':distribution([r['reported_quantity'] for r in rows],Decimal('0.0001')),
            'reported_unit_rate_distribution_rub':distribution([r['reported_rate_rub'] for r in rows],Decimal('0.001')),
            'reported_amount_distribution_rub':distribution([r['reported_amount_rub'] for r in rows],Decimal('0.001')),
            'basis':'EXPLICIT_ONE_CUMULATIVE_REPORTED_ROW_PER_DISTINCT_CASE',
            'small_sample_warning':len(rows)<5,'comparability_independently_verified':False,
            'actual_amounts_independently_verified':False,'contract_execution_verified':False,
            'approved_norm':False,'recommended_rate':None,'inputs_stored':False,'external_submission_allowed':False}
