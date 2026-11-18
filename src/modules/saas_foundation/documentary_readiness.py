"""Read-only tenant documentary review; not a certificate of eligibility."""
from pathlib import Path

from src.modules.company_profile_store.application_checklist import review_application
from src.modules.company_profile_store.qualification_readiness import review_profile
from src.modules.saas_foundation.service import legal_required, owned_run, role_required

PROFILE_CODES={
    'current_registry':'registry','sme_membership':'sme','current_tax':'tax',
    'completed_experience':'experience','license_scope_review':'license',
    'certificate_scope_review':'certificate','sro_scope_review':'sro',
}


def _authorize(session,principal):
    role_required(principal,'owner','admin','analyst')
    legal_required(session,principal)


def _claim(row):
    # No file paths, source references, arbitrary profile values or original bytes.
    return {key:row.get(key) for key in ('requirement_code','kind','state','claim_assertion',
        'fact_version','document_version','observed_on','semantic_verified','legal_satisfied')}


def profile_readiness(session,principal,root:Path):
    _authorize(session,principal)
    p=review_profile(session,customer_id=principal.customer_id,root=root,requirements=PROFILE_CODES)
    return {'contract':'tenant_documentary_readiness_v1','customer_id':principal.customer_id,
            'assessment_date':p['assessment_date'],'screening_preferences_state':p['screening_preferences_state'],
            'requirements':[_claim(r) for r in p['requirements']],
            'documented_claim_count':p['documented_claim_count'],'official_registry_checked':False,
            'legal_eligibility':'NOT_ASSESSED','qualification_verified':False,
            'external_action_allowed':False,'recommendation':'DEFER'}


def run_readiness(session,principal,root:Path,run_id,scenario):
    _authorize(session,principal)
    owned_run(session,principal,run_id)
    result=review_application(session,customer_id=principal.customer_id,root=root,run_id=run_id,
                              signatory=scenario.signatory,goods_used=scenario.goods_used)
    rows=[{**{k:r[k] for k in ('code','title','category','applicability','state','satisfied')},
           'documentary_candidates':[_claim(c) for c in r['documentary_candidates']]}
          for r in result['rows']]
    return {'contract':'tenant_archived_application_readiness_v1','customer_id':principal.customer_id,
            'run_id':run_id,'procurement_number':result['procurement_number'],'status':result['status'],
            'signatory':scenario.signatory,'goods_used':scenario.goods_used,'rows':rows,
            'whole_requirements_complete':False,'current_revision_attested':False,
            'qualification_verified':False,'application_ready':False,'external_action_allowed':False,
            'recommendation':'DEFER'}
