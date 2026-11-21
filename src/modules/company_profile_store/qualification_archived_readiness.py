"""Reviewed archived SME requirements and private tenant evidence readiness."""
from __future__ import annotations

from src.modules.tender_operator_agent_demo.evidence_document_search import (
    checked_search_run,
)
from src.modules.tender_operator_agent_demo.evidence_ri223_archive import (
    ri223_archive_observation,
)
from src.modules.tender_operator_agent_demo.ri223_container_evidence import (
    container_projection_scope,
)
from src.modules.tender_operator_agent_demo.ri223_owner_review import sme_observation
from src.modules.tender_operator_agent_demo.ri223_review_dossier import (
    verified_inventory,
)
from src.modules.tender_operator_agent_demo.verified_original_quote import (
    verify_operator_run_quote,
)

from .qualification_readiness import review_profile

_NOTICES={
    '32616445632':('066252cac6ba7d9bfc876c9ac9a5e5425df31497fe37683dd7cdc5bdf4fa2558',
        'Настоящее извещение информируют о заключении договора с единственным поставщиком и не предназначено для приглашения исполнителей подавать заявки на участие в закупке, участниками закупки могут быть только субъекты малого и среднего предпринимательства.'),
    '32616445866':('a8645964df2203e09abb34dd9d64b88c8bea607031ebde80ff89362914979550',
        'Закупка проводится только для субъектов малого и среднего предпринимательства'),
}


def observe_requirement(run_id):
    run,meta=checked_search_run(run_id)
    n=meta.get('procurement_id')
    unknown={'status':'UNKNOWN','procurement_number':n,'requirement_code':None,
             'current_revision_attested':False,'invitation_to_bid_verified':False}
    if n not in {*_NOTICES,'32616445795'}:
        return unknown
    with container_projection_scope():
        notice=ri223_archive_observation(run,meta)
        inv=verified_inventory(run,meta)
        if not inv['archived_bytes_complete'] or not inv['projection_complete'] or notice['status']!='PINNED_RI223_ARCHIVED_NOTICE':
            return unknown
        if n=='32616445795':
            obs=sme_observation(run_id,run,meta)
            ev=obs.get('source') if obs['status']=='ARCHIVED_CUSTOMER_PARTICIPANT_SME_CLAUSE' else None
            context='MARKET_RESEARCH_ONLY'
        else:
            sha,q=_NOTICES[n]
            matches=[f for f in meta['files'] if f.get('source')=='ri223_attachment'
                     and f.get('data_platform_source',{}).get('canonical_uri')=='tender-upload://'+sha]
            if len(matches)!=1:
                return unknown
            packet=verify_operator_run_quote(run_id=run_id,file_id=matches[0]['file_id'],exact_quote=q)
            ev=packet.get('evidence')
            if not (packet.get('status')=='literal_quote_found_in_extracted_original_only'
                    and isinstance(ev,dict) and ev.get('original_sha256')==sha and ev.get('quote')==q
                    and ev.get('file_id')==matches[0]['file_id'] and ev.get('chunk_id')):
                return unknown
            context='NONCOMPETITIVE_NOTICE_ONLY'
        current,latest=checked_search_run(run_id)
        if not ev or current!=run or latest!=meta or verified_inventory(run,meta)!=inv or ri223_archive_observation(run,meta)!=notice:
            return unknown
    return {**unknown,'status':'ARCHIVED_SME_REQUIREMENT_ATTESTED','requirement_code':'sme_membership',
            'kind':'sme','procedure_context':context,'source':ev,'whole_requirements_complete':False}


def review_archived_profile(session, *, customer_id, root, run_id, now=None):
    requirement=observe_requirement(run_id)
    needed={'sme_membership':'sme'} if requirement['status']=='ARCHIVED_SME_REQUIREMENT_ATTESTED' else {}
    profile=review_profile(session,customer_id=customer_id,root=root,requirements=needed,now=now)
    return {'status':'ARCHIVED_REQUIREMENT_PROFILE_REVIEW_ONLY','requirement':requirement,
            'profile_readiness':profile,'legal_eligibility':'NOT_ASSESSED','recommendation':'DEFER',
            'whole_requirements_complete':False,'go_eligible':False,'external_action_allowed':False}
