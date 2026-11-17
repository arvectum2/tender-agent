"""Case-bound PRICE-01 historical protocol evidence, not a quotation.

Only reviewed repository receipts are price sources. No arbitrary client
amounts, cross-procedure equivalence inferred from titles, or contract prices
substituted from winning offers.
"""
from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.modules.saas_foundation import company_portfolio as portfolio
from src.modules.saas_foundation.service import legal_required, role_required
from src.modules.tender_operator_agent_demo.operator_price_context import (
    archived_competitive_price_context,
    archived_website_price_cohort,
    archived_website_workload_normalization,
)
from src.tender_research.competitive_bid_protocol import AKSAY

Registry = Annotated[str, Field(pattern=r'^[0-9]{19}$',min_length=19,max_length=19)]


class Selection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    reference_registry_number: Registry
    selected_registry_numbers: list[Registry]=Field(min_length=1,max_length=6)
    confirm_review_source_scope: Literal[True]

    @model_validator(mode='after')
    def distinct(self):
        if len(set(self.selected_registry_numbers))!=len(self.selected_registry_numbers):
            raise ValueError('Duplicate procurement')
        if self.reference_registry_number not in self.selected_registry_numbers:
            raise ValueError('Include the explicit reference procurement')
        return self


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def _archives():
    cohort=archived_website_price_cohort()
    workload=archived_website_workload_normalization()
    baseline=archived_competitive_price_context(AKSAY)
    rows={r['registry_number']:r for r in cohort['cases']}
    facts={r['registry_number']:r for r in workload['cases']}
    for number,row in facts.items():
        if number not in rows or rows[number]['original_tz_docx_sha256']!=row['original_technical_scope_docx_sha256']:
            raise HTTPException(503,'Historical scope provenance mismatch')
    if (baseline['evidence']['eis_original_zip_sha256']!=rows[AKSAY]['eis_original_zip_sha256']
        or baseline['evidence']['eis_original_xml_sha256']!=rows[AKSAY]['original_final_xml_sha256']
        or baseline['admitted_count']!=rows[AKSAY]['admitted']
        or baseline['rejected_count']!=rows[AKSAY]['rejected']
        or any(Decimal(baseline['admitted_only_prices_rub'][k])!=Decimal(rows[AKSAY][v]) for k,v in (
            ('min','admitted_price_low_rub'),('median','admitted_price_median_rub'),('max','admitted_price_high_rub')))):
        raise HTTPException(503,'Historical protocol provenance mismatch')
    return cohort,workload,baseline,rows,facts


def _scope_comparison(reference,candidate):
    if reference is None or candidate is None:return []
    a={x['dimension']:x for x in reference['verified_dimensions']}
    b={x['dimension']:x for x in candidate['verified_dimensions']}
    out=[]
    for key in sorted(a.keys()|b.keys()):
        x,y=a.get(key),b.get(key)
        state='UNKNOWN_ON_ONE_SIDE' if x is None or y is None else (
            'SAME_REPORTED_DIMENSION' if all(x[k]==y[k] for k in ('source_value','unit','constraint_kind')) else 'DIFFERENT_REPORTED_DIMENSION')
        out.append({'dimension':key,'state':state,'reference':x,'candidate':y})
    return out


def _record(row,scope,baseline):
    number=row['registry_number']
    return {'registry_number':number,'source_platform':'eis','currency':'RUB',
            'subject':row['original_notice_subject'],'total_offers':row['total'],'admitted_offers':row['admitted'],'rejected_offers':row['rejected'],
            'admitted_price_status':row['admitted_price_status'],
            'admitted_protocol_prices_rub':{'minimum':row['admitted_price_low_rub'],'median':row['admitted_price_median_rub'],'maximum':row['admitted_price_high_rub']},
            'sub_ruble_offer_observed':row['sub_ruble_source_bid_observed'],
            'winner_offer_rub':baseline['winner_price_rub'] if number==AKSAY else None,
            'signed_contract_price_rub':None,'signed_contract_evidence_state':'NOT_PROVIDED_IN_REVIEWED_ARCHIVE',
            'source_scope_state_relative_to_aksay':row['original_scope_comparison_state'],
            'source_scope_reason_relative_to_aksay':row['original_scope_comparison_reason'],
            'scope_anchors':row['scope_original_anchors'],
            'provenance':{k:row[k] for k in ('eis_original_zip_sha256','original_final_xml_sha256','original_tz_docx_sha256')},
            'scope_dimensions':scope['verified_dimensions'] if scope else [],
            'exact_completed_work_quantity':None,'work_quantity_unit':None,
            'normalized_unit_rate_rub':None,'quantity_evidence_state':'NO_VERIFIED_EXACT_COMPLETE_SCOPE_QUANTITY'}


def _context(session,principal,case_id):
    role_required(principal,'owner','admin','analyst')
    legal_required(session,principal)
    case=portfolio._view(session,principal,portfolio._owned_case(session,principal,case_id))
    return {'customer_id':principal.customer_id,'case_id':case_id,'target_source_platform':case['source_platform'],
            'target_external_id':case['external_id'],'target_scope_verified':False}


def catalog(session,principal,case_id):
    context=_context(session,principal,case_id)
    cohort,workload,baseline,rows,facts=_archives()
    result={**context,'schema':'company_historical_comparable_catalog_v1','archive_scope':'SIX_REVIEWED_EIS_WEBSITE_PROCEDURES',
            'cohort_receipt_sha256':cohort['source_cohort_receipt_sha256'],'workload_receipt_sha256':workload['receipt_sha256'],
            'records':[_record(row,facts.get(number),baseline) for number,row in rows.items()],
            'signed_contract_prices_verified_count':0,'current_market_price':None,'recommendation':None,'external_submission_allowed':False}
    return {**result,'catalog_sha256':_digest(result)}


def preview(session,principal,case_id,payload):
    context=_context(session,principal,case_id)
    cohort,workload,baseline,rows,facts=_archives()
    reference=payload.reference_registry_number
    if any(number not in rows for number in payload.selected_registry_numbers):
        raise HTTPException(404,'Historical source not present in reviewed archive')
    observations=[]
    for number in payload.selected_registry_numbers:
        record=_record(rows[number],facts.get(number),baseline)
        # Archive relations to Aksay are not transitive evidence of equivalence.
        state='REFERENCE_ONLY' if number==reference else (
            rows[number]['original_scope_comparison_state'] if reference==AKSAY else 'PAIRWISE_SCOPE_NOT_REVIEWED')
        observations.append({**record,'comparison_state':state,
            'scope_comparison':_scope_comparison(facts.get(reference),facts.get(number)) if number!=reference else [],
            'accepted_for_cross_procurement_normalization':False})
    exact_target=context['target_source_platform']=='eis' and context['target_external_id']==reference
    result={**context,'schema':'company_historical_comparable_preview_v1','reference_registry_number':reference,
            'target_reference_identity_matches':exact_target,
            'cohort_receipt_sha256':cohort['source_cohort_receipt_sha256'],'workload_receipt_sha256':workload['receipt_sha256'],
            'selected_distinct_procurements':len(observations),'observations':observations,
            'admitted_price_procedures_count':sum(x['admitted_protocol_prices_rub']['median'] is not None for x in observations),
            'signed_contract_prices_verified_count':0,'reference_procurements_count':1,
            'additional_equivalent_procurements':0,'normalization_state':'INSUFFICIENT_VERIFIED_EQUIVALENT_SCOPE_AND_QUANTITY',
            'normalized_admitted_offer_range_rub':None,'normalized_signed_contract_range_rub':None,
            'cross_procurement_price_rub':None,'current_market_price':None,'recommendation':None,
            'win_probability':None,'inputs_stored':False,'external_submission_allowed':False}
    return {**result,'preview_sha256':_digest(result)}


def exact_unit_amount(price:Decimal,quantity:Decimal)->Decimal:
    """Internal arithmetic only, NOT a comparability or source verifier.

    Caller must establish exact positive quantity covering the entire price,
    identical scope and unit, price basis and currency from reviewed evidence.
    No archive record currently meets those quantity requirements.
    """
    if not isinstance(price,Decimal) or not isinstance(quantity,Decimal) or not price.is_finite() or not quantity.is_finite() or price<=0 or quantity<=0 or price>Decimal('999999999999.99') or quantity>Decimal('999999999.9999') or quantity<Decimal('0.0001'):
        raise ValueError('Bounded positive exact source quantities and prices required')
    with localcontext() as ctx:
        ctx.prec=40
        if price!=price.quantize(Decimal('.01')) or quantity!=quantity.quantize(Decimal('.0001')):
            raise ValueError('Unsupported source precision')
        return (price/quantity).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP)
