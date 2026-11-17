"""Read-only access to the exact repository-approved publication release."""
from pathlib import Path

from fastapi import HTTPException

from src.modules.saas_foundation.company_historical_comparables import _context
from src.tender_research.reviewed_contract_evidence import sealed
from src.tender_research.reviewed_contract_registry import (
    MAX_RELEASE,
    load_release,
    public_projection,
)

_RELEASE_PATH=Path(__file__).resolve().parents[3]/'docs/roadmap/price01_contract_registry/release.json'
_RELEASE_SHA256='015d0d6e0b9b78dc25413189d533919e8f8353886723869315a85245bd051321'


def _approved_release():
    try:
        if _RELEASE_PATH.is_symlink() or not _RELEASE_PATH.is_file():raise ValueError('Release unavailable')
        with _RELEASE_PATH.open('rb') as f:raw=f.read(MAX_RELEASE+1)
        return load_release(raw,_RELEASE_SHA256)
    except (ValueError,OSError,RecursionError) as exc:
        raise HTTPException(503,'Reviewed contract release unavailable') from exc


def catalog(session,principal,case_id):
    context=_context(session,principal,case_id)
    release=_approved_release()
    projection=public_projection(release,_RELEASE_SHA256)
    groups=[]
    for value in projection['active_groups']:
        value=dict(value)
        value['target_reference_identity_matches']=(context['target_source_platform']=='eis' and context['target_external_id']==value['reference_registry_number'])
        value['target_scope_equivalence_verified']=False
        groups.append(value)
    result={**context,'schema':'company_reviewed_contract_registry_v1',**projection,'active_groups':groups,
            'basis':'REVIEWER_ATTESTED_SIGNED_CONTRACT_PRICE_PER_EXACT_CONTRACTED_FULL_SCOPE_UNIT',
            'independent_signature_verification':False,'source_authenticity_independently_verified':False,
            'contract_execution_verified':False,'completed_work_quantity_verified':False,
            'cross_group_range_rub':None,'current_market_price':None,'recommendation':None,'external_submission_allowed':False}
    return {**result,'catalog_sha256':sealed(result)}
