"""Source-derived private plan and independent structural coverage review.

Caller authorizes customer and archive run. No production or outbound action.
Owner approval binds the exact derived plan, not legal eligibility.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from src.modules.company_profile_store.application_checklist import (
    _rows,
    observe_application,
)
from src.modules.tender_operator_agent_demo.ri223_application_source import (
    SOURCE_PARAGRAPHS,
)

from .private_review_bundle import (
    ReviewPlan,
    build_private_review_bundle,
    verify_private_review_bundle,
)
from .source_bound_fill import _utc

_ROLE = {'DRAFT':'FORM','ATTACHMENT':'DOCUMENT','EVIDENCE_ALTERNATIVES':'ALTERNATIVES',
         'DECLARATION':'DECLARATION','CROSS_REFERENCE':'CROSS_REFERENCE','WARNING':'CROSS_REFERENCE'}
_APPLICABILITY = {'REQUIRED':'REQUIRED','REQUIRED_IN_SCENARIO':'REQUIRED',
                  'CONDITIONAL_UNKNOWN':'CONDITIONAL_UNKNOWN','NOT_TRIGGERED_IN_SCENARIO':'NOT_TRIGGERED',
                  'OPTIONAL_EVIDENCE_NOT_OPTIONAL_RIGHTS':'OPTIONAL_EVIDENCE','REVIEW_REQUIRED':'CONDITIONAL_UNKNOWN'}


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _validate_source(packet):
    if packet.get('status')!='ARCHIVED_QUOTATION_CHECKLIST_REVIEW_ONLY' or packet.get('procurement_number')!='32616444788':
        raise ValueError('Reviewed archived quotation source required')
    groups=packet.get('source_groups',{})
    if set(groups)!=set(SOURCE_PARAGRAPHS):
        raise ValueError('Source document coverage mismatch')
    for sha,expected in SOURCE_PARAGRAPHS.items():
        g=groups[sha]
        if set(g)!=set(expected):
            raise ValueError('Source paragraph coverage mismatch')
        files=set()
        for key,quote in expected.items():
            fragments=g[key]
            if not fragments or any(f.get('original_sha256')!=sha or not f.get('file_id') or not f.get('chunk_id')
                                    or not isinstance(f.get('quote'),str) for f in fragments):
                raise ValueError('Source fragment lineage incomplete')
            if ' '.join(f['quote'] for f in fragments)!=quote:
                raise ValueError('Source literal coverage mismatch')
            files.update(f['file_id'] for f in fragments)
        if len(files)!=1:
            raise ValueError('Mixed source file identities')


def _derive(packet,*,customer_id,run_id,signatory,goods_used):
    _validate_source(packet)
    rows=_rows(packet,signatory,goods_used)
    source_hash=digest(packet['source_groups'])
    items=[]
    requirements={}
    for r in rows:
        key=r['code']
        requirements[key]={'source_sha256':digest(r['source']),'original_applicability':r['applicability'],
                           'title':r['title'],'derived_from':key}
        items.append({'code':key,'role':_ROLE[r['category']],'applicability':_APPLICABILITY[r['applicability']],
                      'review_ref':'source-sha256:'+requirements[key]['source_sha256'],'claims':r['claims']})
    # Price is an additional output component of the quotation form, not a
    # separately asserted mandatory customer attachment.
    parent=requirements['application_form']
    requirements['price_component']={**parent,'derived_from':'application_form',
                                    'title':'Проект цены: составная часть котировочной заявки'}
    items.append({'code':'price_component','role':'PRICE','applicability':'REQUIRED',
                  'review_ref':'source-sha256:'+parent['source_sha256'],'claims':{}})
    scope={'customer_id':customer_id,'run_id':run_id,'procurement_ref':packet['procurement_number'],
           'source_sha256':source_hash,'signatory_scenario':signatory,'goods_use_scenario':goods_used,
           'requirements':requirements,'items':items}
    approved_digest=digest(scope)
    plan=ReviewPlan(procurement_ref=packet['procurement_number'],plan_review_ref='checklist-sha256:'+approved_digest,
                    owner_reviewed_plan=False,items=items)
    return plan,scope,approved_digest


def preview_plan(*,customer_id,run_id,signatory='UNKNOWN',goods_used=None):
    plan,scope,sha=_derive(observe_application(run_id),customer_id=customer_id,run_id=run_id,
                           signatory=signatory,goods_used=goods_used)
    return {'plan':plan.model_dump(mode='json'),'scope':scope,'approval_digest':sha,
            'application_ready':False,'whole_requirements_complete':False}


def _approved(*,customer_id,run_id,signatory,goods_used,approved_digest):
    plan,scope,sha=_derive(observe_application(run_id),customer_id=customer_id,run_id=run_id,
                           signatory=signatory,goods_used=goods_used)
    if sha!=approved_digest:
        raise ValueError('Exact source-derived plan approval required')
    return plan.model_copy(update={'owner_reviewed_plan':True}),scope


def bundle_inputs_digest(*,approved_digest,templates,selections,cost=None,offer_terms=None,declaration_terms=None):
    """Pin exact private input bytes and reviewed structured terms, not authority."""
    return digest({'schema':'checklist-bundle-inputs-v1','plan_approval_digest':approved_digest,
                   'templates':{k:{'bytes_sha256':hashlib.sha256(raw).hexdigest(),
                                   'mapping':mapping.model_dump(mode='json')} for k,(raw,mapping) in templates.items()},
                   'selections':selections,'cost':cost.model_dump(mode='json') if cost is not None else None,
                   'offer_terms':offer_terms.model_dump(mode='json') if offer_terms is not None else None,
                   'declaration_terms':declaration_terms.model_dump(mode='json') if declaration_terms is not None else None})


def build_from_checklist(session,*,customer_id,root,run_id,approved_digest,approved_inputs_digest,templates,selections,
                         signatory='UNKNOWN',goods_used=None,cost=None,offer_terms=None,declaration_terms=None,now=None):
    now=_utc(now or datetime.now(UTC))
    plan,scope=_approved(customer_id=customer_id,run_id=run_id,signatory=signatory,
                         goods_used=goods_used,approved_digest=approved_digest)
    inputs={'approved_digest': approved_digest,'templates': templates,'selections': selections,'cost': cost,
                'offer_terms': offer_terms,'declaration_terms': declaration_terms}
    if bundle_inputs_digest(**inputs)!=approved_inputs_digest:
        raise ValueError('Exact bundle input approval required')
    raw,manifest=build_private_review_bundle(session,customer_id=customer_id,root=root,plan=plan,
        templates=templates,selections=selections,cost=cost,offer_terms=offer_terms,
        declaration_terms=declaration_terms,now=now)
    # A second source observation refuses changed sources or applicability.
    again,_=_approved(customer_id=customer_id,run_id=run_id,signatory=signatory,
                      goods_used=goods_used,approved_digest=approved_digest)
    if again!=plan:
        raise ValueError('Reviewed plan changed during assembly')
    if bundle_inputs_digest(**inputs)!=approved_inputs_digest:
        raise ValueError('Reviewed bundle inputs changed during assembly')
    sha=hashlib.sha256(raw).hexdigest()
    gate=assess_coverage(raw,expected_sha256=sha,plan=plan,scope=scope)
    return raw,{'archive_sha256':sha,'plan_approval_digest':approved_digest,'inputs_approval_digest':approved_inputs_digest,
                'manifest':manifest,'coverage_review':gate}


def assess_coverage(raw,*,expected_sha256,plan,scope):
    """Independent pass over exact expected plan and member inventory.
    This is structural review, not semantic/legal or current-fact re-attestation.
    """
    if not plan.owner_reviewed_plan or plan.plan_review_ref!='checklist-sha256:'+digest(scope):
        raise ValueError('Expected reviewed scope mismatch')
    if plan.procurement_ref!=scope['procurement_ref'] or [i.model_dump(mode='json') for i in plan.items]!=scope['items']:
        raise ValueError('Expected plan differs from approved source scope')
    if not expected_sha256:
        raise ValueError('Independent archive digest required')
    m=verify_private_review_bundle(raw,expected_sha256=expected_sha256)
    if (m['customer_id']!=scope['customer_id'] or m['procurement_ref']!=plan.procurement_ref
            or m['plan_review_ref']!=plan.plan_review_ref):
        raise ValueError('Bundle scope mismatch')
    expected={i.code:i for i in plan.items}
    rows={r['code']:r for r in m['items']}
    if set(rows)!=set(expected) or set(rows)!=set(scope['requirements']):
        raise ValueError('Bundle omitted or added source requirement')
    inventory={x['path']:x for x in m['inventory']}
    report=[]
    for code,item in expected.items():
        row=rows[code]
        if (row['role'],row['applicability'],row['review_ref'])!=(item.role,item.applicability,item.review_ref):
            raise ValueError('Requirement projection changed')
        paths=row['paths']
        roles={inventory[p]['role'] for p in paths}
        if item.applicability=='NOT_TRIGGERED':
            if paths or row['state']!='NOT_TRIGGERED_IN_SCENARIO':
                raise ValueError('Non-triggered item contains output')
            reasons=[]
        else:
            if row['state']=='NOT_TRIGGERED_IN_SCENARIO':
                raise ValueError('Active requirement silently excluded')
            reasons=['HUMAN_REVIEW_REQUIRED']
            if item.applicability=='CONDITIONAL_UNKNOWN':
                reasons.append('APPLICABILITY_OR_CROSS_REFERENCE_UNRESOLVED')
            expected_roles={'FORM':{'DRAFT_FORM'},'DOCUMENT':{'DOCUMENTARY_CANDIDATE'},
                'ALTERNATIVES':{'DOCUMENTARY_CANDIDATE'},'DECLARATION':{'UNSIGNED_DECLARATIONS'},
                'PRICE':{'INTERNAL_SCENARIO','UNSIGNED_OFFER'},'CROSS_REFERENCE':set()}[item.role]
            if roles-expected_roles or len(paths)!=len(roles):
                raise ValueError('Unexpected output role or duplicate output')
            allowed_paths={'DRAFT_FORM':{f'forms/{code}.docx',f'forms/{code}.xlsx'},
                'DOCUMENTARY_CANDIDATE':{f'evidence/{code}.pdf'},
                'UNSIGNED_DECLARATIONS':{'drafts/declarations.docx'},
                'UNSIGNED_OFFER':{'drafts/price-offer.docx'},
                'INTERNAL_SCENARIO':{'internal/price-scenario.json'}}
            if any(p not in allowed_paths[inventory[p]['role']] for p in paths):
                raise ValueError('Output path does not match reviewed role')
            if item.role=='FORM':
                if not paths:
                    reasons.append('FORM_MISSING')
                else:
                    r=row.get('field_receipt',{})
                    fs=r.get('fields',[])
                    if (r.get('customer_id')!=scope['customer_id'] or r.get('output_sha256')!=inventory[paths[0]]['sha256']
                            or r.get('mapping_exhaustive') is not False or not fs
                            or r.get('unknown_count')!=sum(f.get('value') is None for f in fs)):
                        raise ValueError('Form receipt inconsistent')
                    if r['unknown_count']:
                        reasons.append('UNKNOWN_IDENTITY_FIELDS')
                    reasons.append('FORM_MAPPING_NOT_EXHAUSTIVE')
            elif item.role in ('DOCUMENT','ALTERNATIVES'):
                if not paths:
                    reasons.append('DOCUMENTARY_CANDIDATE_MISSING')
                else:
                    r=row.get('source',{})
                    if (row.get('selected_claim') not in item.claims or r.get('requirement_code')!=row['selected_claim']
                            or r.get('claim_assertion')!='PRESENT' or r.get('document_sha256')!=inventory[paths[0]]['sha256']):
                        raise ValueError('Document candidate receipt mismatch')
                    reasons.append('DOCUMENT_SEMANTICS_UNVERIFIED')
            elif item.role=='DECLARATION':
                if not paths:
                    reasons.append('DECLARATIONS_MISSING')
                else:
                    r=row.get('declaration_receipt',{})
                    if not r.get('rows') or r.get('unanswered_count')!=sum(x.get('source') is None for x in r['rows']):
                        raise ValueError('Declaration receipt mismatch')
                    if r['unanswered_count']:
                        reasons.append('UNANSWERED_DECLARATIONS')
                    reasons.append('DECLARATION_LEGAL_REVIEW_REQUIRED')
            elif item.role=='PRICE':
                if 'UNSIGNED_OFFER' not in roles:
                    reasons.append('OFFER_MISSING_OR_UNCONFIRMED')
                elif 'INTERNAL_SCENARIO' not in roles or not row.get('offer_receipt',{}).get('source'):
                    raise ValueError('Offer without scenario or confirmation')
                reasons.append('COMMERCIAL_AND_TAX_REVIEW_REQUIRED')
            else:
                reasons.append('REQUIREMENT_REVIEW_OPEN')
        report.append({'code':code,'derived_from':scope['requirements'][code]['derived_from'],
                       'source_sha256':scope['requirements'][code]['source_sha256'],
                       'output_count':len(paths),'reasons':reasons})
    return {'status':'STRUCTURAL_COVERAGE_REVIEW_ONLY','archive_sha256':expected_sha256,
            'reviewed_source_row_count':len({r['derived_from'] for r in report}),
            'plan_item_count':len(report),'items':report,
            'open_item_count':sum(bool(r['reasons']) for r in report),
            'whole_requirements_complete':False,'current_facts_reattested':False,
            'semantic_eligibility_verified':False,'application_ready':False,
            'recommendation':'DEFER','go_eligible':False,'external_action_allowed':False}
