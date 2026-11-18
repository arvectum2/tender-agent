"""Local operator review only: historical owner evidence and explicit economics."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from src.modules.company_profile_store.qualification_references import (
    CompletedContractReferenceSnapshot,
)

from .evidence_document_search import checked_search_run
from .evidence_ri223_archive import ri223_archive_observation
from .operator_cashflow_calendar import CashCalendarRequest, calculate_cash_calendar
from .operator_cost_scenarios import (
    ExplicitCostScenarioRequest,
    calculate_explicit_cost_thresholds,
)
from .ri223_attachment_evidence import digest, read_bytes, verified_container_lineage
from .ri223_container_evidence import container_projection_scope
from .ri223_contract_risk import observe_contract_risk
from .ri223_review_dossier import verified_inventory
from .ri223_review_scoring import scoring_observation
from .verified_original_quote import verify_operator_run_quote

_ROOT=Path(__file__).resolve().parents[3]
_OWNER_RECEIPT=_ROOT/'docs/acceptance/arvectum_owner_reference_list_and_czn_2026-10-13.json'
_OWNER_SHA='459b254494b1b79b58be17f159b97496fd694373a743d67adab035ce21e0dbe5'
_SME_MEMBER='3727-МИ/Извещение.docx'
_SME_SHA='366fc747cd6d77f846fe95f422d3a81abf5d0899c74111f90af5e07614df18ef'
_SME_QUOTE='участниками маркетинговых исследований могут быть только субъекты малого и среднего предпринимательства'


def historical_owner_reference() -> dict:
    """Only the pinned dated statement, not a live CompanyProfile fact."""
    empty={'status':'UNKNOWN','current_reference_count':None,'current_profile_bound':False}
    try:
        raw=read_bytes(_OWNER_RECEIPT,32768)
        if digest(raw)!=_OWNER_SHA:
            return empty
        doc=json.loads(raw)
        if doc['company']!='ООО «Арвектум»' or doc['reference_fact_source_type']!='CUSTOMER_PROVIDED':
            return empty
        snapshot=CompletedContractReferenceSnapshot.model_validate(doc['reference_fact_value'])
        if not snapshot.owner_confirmed or snapshot.completeness!='COMPLETE':
            return empty
        return {**empty,'status':'HISTORICAL_OWNER_STATEMENT_ONLY',
                'company':doc['company'],'as_of_date':snapshot.as_of_date.isoformat(),
                'historical_completed_count':sum(c.completed for c in snapshot.contracts),
                'receipt_sha256':_OWNER_SHA,'source_ref':doc['reference_fact_source_ref'],
                'cryptographic_signature_verified':False}
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return empty


def sme_observation(run_id: str, run: Path, metadata: dict) -> dict:
    """Narrow original-source requirement, not a registry/legal eligibility check."""
    empty={'status':'UNKNOWN','supplier_membership':'UNKNOWN','eligibility':'NOT_ASSESSED'}
    if metadata.get('procurement_id')!='32616445795':
        return empty
    matches=[f for f in metadata['files'] if f.get('source')=='ri223_container_member'
             and f.get('ri223_container',{}).get('member_path')==_SME_MEMBER]
    if len(matches)!=1:
        return empty
    row=matches[0]
    lineage=verified_container_lineage(run,metadata,row)
    if not lineage or lineage['member_sha256']!=_SME_SHA:
        return empty
    checked=verify_operator_run_quote(run_id=run_id,file_id=row['file_id'],exact_quote=_SME_QUOTE)
    evidence=checked.get('evidence')
    if (checked.get('status')!='literal_quote_found_in_extracted_original_only' or not evidence
            or evidence.get('original_sha256')!=_SME_SHA or evidence.get('quote')!=_SME_QUOTE
            or evidence.get('ri223_container')!=lineage):
        return empty
    return {**empty,'status':'ARCHIVED_CUSTOMER_PARTICIPANT_SME_CLAUSE',
            'actor':'PARTICIPANT','source':evidence,'registry_check_performed':False}


def lot_scenario(notice: dict, scenario: ExplicitCostScenarioRequest | None) -> dict:
    """Use PRICE01 once; compare only an independently pinned single RUB lot."""
    unknown={'status':'UNKNOWN','actual_costs_verified':False,'actual_tax_verified':False,
             'actual_security_verified':False,'commercial_owner_go':False}
    if scenario is None:
        return {**unknown,'reason':'EXPLICIT_COST_INPUT_REQUIRED'}
    if (notice.get('status')!='PINNED_RI223_ARCHIVED_NOTICE' or notice.get('lot_count')!=1
            or notice.get('fields',{}).get('single_lot_currency')!='RUB'
            or 'single_lot_initial_sum' not in notice['fields']):
        return {**unknown,'reason':'VERIFIED_SINGLE_RUB_LOT_REQUIRED'}
    ceiling=Decimal(notice['fields']['single_lot_initial_sum'])
    if ceiling<=0:
        return {**unknown,'reason':'POSITIVE_ARCHIVED_PRICE_REQUIRED'}
    packet=calculate_explicit_cost_thresholds(scenario)
    offer=packet.get('offer_scenario')
    return {**unknown,'status':'ARCHIVED_LOT_EXPLICIT_SCENARIO_ONLY',
            'archived_lot_initial_sum_rub':format(ceiling,'f'),
            'source':notice['citations'],
            'calculation':packet,
            'offer_within_archived_initial_sum':Decimal(offer['offer_price_rub'])<=ceiling if offer else None,
            'target_threshold_within_archived_initial_sum':Decimal(packet['full_cost_plus_explicit_target_rub'])<=ceiling,
            'current_price_limit_attested':False}


def review_archived_owner_run(run_id: str, scenario: ExplicitCostScenarioRequest | None=None, *, include_decision: bool=False, cash_calendar: CashCalendarRequest | None=None) -> dict:
    """Operator-local, no arbitrary customer ID, database, persistence or HTTP route."""
    run,metadata=checked_search_run(run_id)
    notice=ri223_archive_observation(run,metadata)
    inventory=verified_inventory(run,metadata) if notice['status']=='PINNED_RI223_ARCHIVED_NOTICE' else None
    base={'run_id':run_id,'status':'UNKNOWN','decision':'NOT_DECIDED','go_eligible':False,
          'external_action_allowed':False,'current_revision_attested':False,'supplier_fit':'UNKNOWN',
          'actual_costs':'UNKNOWN','current_profile_binding':'NOT_ESTABLISHED',
          'legal_eligibility':'NOT_ASSESSED','competitive_recommendation':'NOT_ASSESSED'}
    if not inventory or not inventory['archived_bytes_complete'] or not inventory['projection_complete']:
        return {**base,'reason':'COMPLETE_PROJECTED_ARCHIVED_ORIGINALS_REQUIRED'}
    owner=historical_owner_reference()
    sme=sme_observation(run_id,run,metadata)
    scoring=scoring_observation(run,metadata)
    calc=lot_scenario(notice,scenario)
    if cash_calendar is not None:
        if scenario is None or calc['status']!='ARCHIVED_LOT_EXPLICIT_SCENARIO_ONLY':
            raise ValueError('Archived single-lot explicit offer required for cash calendar')
        calc['cash_calendar']=calculate_cash_calendar(scenario,cash_calendar)

    with container_projection_scope():
        risks=observe_contract_risk(run_id,run,metadata,calc)
    combined={}
    if include_decision:
        from .ri223_decision_review import archived_decision_projection
        from .ri223_review_dossier import build_archived_review

        dossier=build_archived_review(run_id,run,metadata)
        projection=archived_decision_projection(notice,inventory,dossier,risks,calc)
        if projection["status"]!="ARCHIVED_DECISION_REVIEW_ONLY":
            return {**base,"reason":"COMBINED_REVIEW_UNVERIFIED"}
        combined={"dossier":dossier,"decision_review":projection}
    current,meta=checked_search_run(run_id)
    if current!=run or meta!=metadata or verified_inventory(run,metadata)!=inventory or ri223_archive_observation(run,metadata)!=notice:
        return {**base,'reason':'SOURCE_CHANGED_DURING_REVIEW'}
    return {**base,**combined,'status':'ARCHIVED_OWNER_REVIEW_ONLY','notice':notice,'inventory':inventory,
            'historical_reference_list':owner,'participant_sme_clause':sme,'scoring':scoring,
            'economics':calc,'contract_risk':risks,'missing_review_inputs':['CURRENT_AUTHORIZED_COMPANY_PROFILE','DATED_SME_REGISTRY_EVIDENCE',
             'APPLIED_LOT_SCORING_FORMULA','ACTUAL_COSTS_AND_PAYMENT_TIMING','OWNER_COMMERCIAL_DECISION']}
