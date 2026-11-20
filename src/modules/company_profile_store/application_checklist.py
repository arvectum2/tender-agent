"""Source-led historical bidder checklist; not a submission package."""
from __future__ import annotations

from typing import Literal

from src.modules.tender_operator_agent_demo.evidence_document_search import (
    checked_search_run,
)
from src.modules.tender_operator_agent_demo.evidence_ri223_archive import (
    ri223_archive_observation,
)
from src.modules.tender_operator_agent_demo.ri223_application_source import (
    SOURCE_PARAGRAPHS,
)
from src.modules.tender_operator_agent_demo.ri223_container_evidence import (
    container_projection_scope,
)
from src.modules.tender_operator_agent_demo.ri223_review_dossier import (
    verified_inventory,
)
from src.modules.tender_operator_agent_demo.ri223_staged_evidence import _attest
from src.modules.tender_operator_agent_demo.verified_original_quote import (
    verify_operator_run_quote,
)

from .qualification_readiness import review_profile

_FORM,_TZ=SOURCE_PARAGRAPHS
_NOTICES={
    '32616445632':('066252cac6ba7d9bfc876c9ac9a5e5425df31497fe37683dd7cdc5bdf4fa2558',
        'Настоящее извещение информируют о заключении договора с единственным поставщиком и не предназначено для приглашения исполнителей подавать заявки на участие в закупке, участниками закупки могут быть только субъекты малого и среднего предпринимательства.'),
    '32616445866':('a8645964df2203e09abb34dd9d64b88c8bea607031ebde80ff89362914979550',
        'Размещение настоящего Извещения носит уведомительный характер – договор заключается с единственным поставщиком (подрядчиком, исполнителем), без проведения конкурен тных процедур, согласно Положению о закупке,'),
    '32616447910':('297e426b920b361ec90b323fdf1444eeb3d709b858216ef14a2aabdb6f07b908',
        'Извещение носит уведомительный характер и не предполагает при его размещении в ЕИС подачу со стороны участников закупки каких-либо заявок, документов, сведений,'),
}
Signatory=Literal['UNKNOWN','DIRECTOR','REPRESENTATIVE','DELEGATED_SIGNER']
_DECLARATIONS=tuple(k for k in SOURCE_PARAGRAPHS[_FORM] if k.startswith('declaration_'))


def observe_application(run_id):
    run,meta=checked_search_run(run_id)
    n=meta.get('procurement_id')
    unknown={'status':'UNKNOWN','procurement_number':n,'source_groups':{},
             'current_revision_attested':False,'whole_application_requirements_complete':False}
    if n not in {*_NOTICES,'32616444788'}:
        return unknown
    with container_projection_scope():
        inv=verified_inventory(run,meta)
        notice=ri223_archive_observation(run,meta)
        if not inv['archived_bytes_complete'] or not inv['projection_complete'] or notice['status']!='PINNED_RI223_ARCHIVED_NOTICE':
            return unknown
        groups=SOURCE_PARAGRAPHS if n=='32616444788' else {_NOTICES[n][0]:{'notification_only':_NOTICES[n][1]}}
        docs={sha:_attest(run_id,run,meta,sha,verifier=verify_operator_run_quote,paragraphs=paragraphs)
              for sha,paragraphs in groups.items()}
        current,latest=checked_search_run(run_id)
        if current!=run or latest!=meta or verified_inventory(run,meta)!=inv or ri223_archive_observation(run,meta)!=notice:
            return unknown
    complete=all(set(docs[sha])==set(groups[sha]) for sha in groups)
    return {**unknown,'source_groups':docs,
            'status':('ARCHIVED_QUOTATION_CHECKLIST_REVIEW_ONLY' if n=='32616444788' else 'ARCHIVED_NOTIFICATION_NOT_APPLICATION')
                     if complete else 'INCOMPLETE_REVIEWED_SOURCE'}


def _rows(packet,signatory: Signatory,goods_used: bool | None):
    if signatory not in ('UNKNOWN','DIRECTOR','REPRESENTATIVE','DELEGATED_SIGNER') or (goods_used is not None and type(goods_used) is not bool):
        raise ValueError('Explicit valid scenario required')
    if packet['status']!='ARCHIVED_QUOTATION_CHECKLIST_REVIEW_ONLY':
        return []
    g=packet['source_groups']
    def row(code,title,category,applicability,keys,*,sha=_FORM,claims=None):
        return {'code':code,'title':title,'category':category,'applicability':applicability,
                'source':{k:g[sha][k] for k in keys},'claims':claims or {},
                'state':'REVIEW_REQUIRED','satisfied':None}
    def condition(needed):
        return 'CONDITIONAL_UNKNOWN' if signatory=='UNKNOWN' else 'REQUIRED_IN_SCENARIO' if needed else 'NOT_TRIGGERED_IN_SCENARIO'
    return [
        row('application_form','Котировочная заявка: реквизиты, цена, условия','DRAFT','REQUIRED',
            ('form_heading','identity_fields','offer_fields','execution_terms')),
        row('goods_description','Описание принимаемых к бухучёту товаров и материалов','DRAFT',
            'CONDITIONAL_UNKNOWN' if goods_used is None else 'REQUIRED_IN_SCENARIO' if goods_used else 'NOT_TRIGGERED_IN_SCENARIO',('goods_condition',)),
        row('declarations','Декларации по образцу заявки и подпись','DECLARATION','REQUIRED',_DECLARATIONS),
        row('director_appointment','Копия решения, избрания или приказа о назначении руководителя','ATTACHMENT','REQUIRED',
            ('appointment',),claims={'director_appointment':'authority'}),
        row('power_of_attorney','Доверенность представителя','ATTACHMENT',condition(signatory in ('REPRESENTATIVE','DELEGATED_SIGNER')),
            ('representation',),claims={'power_of_attorney':'authority'}),
        row('delegated_signer_authority','Подтверждение полномочий подписанта доверенности','ATTACHMENT',condition(signatory=='DELEGATED_SIGNER'),
            ('representation',),claims={'delegated_signer_authority':'authority'}),
        row('software_distribution_rights','Право распространения СПС; письмо правообладателя ИЛИ свидетельство партнёра','EVIDENCE_ALTERNATIVES','OPTIONAL_EVIDENCE_NOT_OPTIONAL_RIGHTS',
            ('rights',),sha=_TZ,claims={'rights_holder_letter':'rights','partner_certificate':'rights'}),
        row('other_tz_documents','Иные документы по ТЗ: открытая проверка полноты','CROSS_REFERENCE','REVIEW_REQUIRED',('tz_reference',)),
        row('rejection_warning','Предупреждение об отклонении за неполную информацию','WARNING','REVIEW_REQUIRED',('reject_warning',)),
    ]


def review_application(session,*,customer_id,root,run_id,signatory: Signatory='UNKNOWN',goods_used: bool|None=None,now=None):
    packet=observe_application(run_id)
    rows=_rows(packet,signatory,goods_used)
    requirements={k:v for row in rows if row['applicability']!='NOT_TRIGGERED_IN_SCENARIO' for k,v in row['claims'].items()}
    profile=review_profile(session,customer_id=customer_id,root=root,requirements=requirements,now=now)
    facts={r['requirement_code']:r for r in profile['requirements']}
    for row in rows:
        row['documentary_candidates']=[facts[k] for k in row['claims'] if k in facts]
        if row['applicability']=='NOT_TRIGGERED_IN_SCENARIO':
            row['state']='NOT_TRIGGERED_IN_SCENARIO'
        elif row['claims']:
            row['state']='CANDIDATE_REVIEW_REQUIRED' if any(f['state']=='DOCUMENTED_OWNER_CLAIM_REVIEW_REQUIRED' and f['claim_assertion']=='PRESENT' for f in row['documentary_candidates']) else 'DOCUMENTARY_EVIDENCE_MISSING_OR_UNCONFIRMED'
    return {'status':packet['status'],'procurement_number':packet['procurement_number'],'source_observation':packet,
            'rows':rows,'signatory_scenario':signatory,'goods_use_scenario':goods_used,
            'whole_application_requirements_complete':False,'application_ready':False,'recommendation':'DEFER',
            'external_action_allowed':False,'go_eligible':False,'signed':False,'submitted':False}
