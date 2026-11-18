"""Private evidence-version approval. Digest binding, not authenticated approval."""
from __future__ import annotations

from datetime import UTC, datetime

from src.modules.company_profile_store.qualification_readiness import review_profile
from src.modules.company_profile_store.service import list_current_company_profile_facts

from .checklist_bundle_gate import (
    _approved,
    build_from_checklist,
    bundle_inputs_digest,
    digest,
)
from .private_review_bundle import verify_private_review_bundle
from .reviewed_commercial_drafts import DeclarationTerms, _assertion, subject_digest
from .source_bound_fill import _resolve, _utc


def _snapshot(session,*,customer_id,root,plan,templates,selections,offer_terms,declaration_terms,now,
              approved_digest,approved_inputs_digest):
    if session.new or session.dirty or session.deleted:
        raise ValueError('Read-only approval requires clean session')
    session.expire_all()
    active={i.code:i for i in plan.items if i.applicability in ('REQUIRED','OPTIONAL_EVIDENCE')}
    if set(templates)-{k for k,i in active.items() if i.role=='FORM'} or set(selections)-{k for k,i in active.items() if i.role in ('DOCUMENT','ALTERNATIVES')}:
        raise ValueError('Unresolved or out-of-scope output')
    keys=set()
    fields={}
    for code,(_,mapping) in templates.items():
        fields[code]=_resolve(session,customer_id,mapping.fields,now)
        keys.update('draft_identity:'+f.field_code for f in mapping.fields)
    requirements={}
    for item in active.values():
        for code,kind in item.claims.items():
            if code in requirements and requirements[code]!=kind:
                raise ValueError('Conflicting claim kind')
            requirements[code]=kind
    profile=review_profile(session,customer_id=customer_id,root=root,requirements=requirements,now=now)
    docs={r['requirement_code']:r for r in profile['requirements']}
    keys.update('qualification_claim:'+k for k in docs)
    selected={}
    for code,claim in selections.items():
        if claim not in active[code].claims:
            raise ValueError('Selection outside reviewed alternatives')
        row=docs[claim]
        if row['state']!='DOCUMENTED_OWNER_CLAIM_REVIEW_REQUIRED' or row['claim_assertion']!='PRESENT':
            raise ValueError('Selected current documentary candidate unavailable')
        selected[code]=row
    offer=None
    if offer_terms is not None:
        if offer_terms.procurement_ref!=plan.procurement_ref:
            raise ValueError('Offer outside reviewed procurement')
        k='draft_offer:'+plan.procurement_ref
        keys.add(k)
        offer={'subject_sha256':subject_digest(offer_terms),
               'source':_assertion(session,customer_id,plan.procurement_ref,k,subject_digest(offer_terms),now)}
    declarations={}
    if declaration_terms is not None:
        if declaration_terms.procurement_ref!=plan.procurement_ref:
            raise ValueError('Declarations outside reviewed procurement')
        for statement in declaration_terms.statements:
            k='draft_declaration:'+statement.code
            if statement.code in declarations:
                raise ValueError('Duplicate declaration code')
            keys.add(k)
            sha=subject_digest(DeclarationTerms(procurement_ref=plan.procurement_ref,statements=[statement]))
            declarations[statement.code]={'subject_sha256':sha,'source':_assertion(session,customer_id,plan.procurement_ref,k,sha,now)}
    facts={f.fact_key:f for f in list_current_company_profile_facts(session,customer_id=customer_id)}
    versions={}
    for k in sorted(keys):
        f=facts.get(k)
        versions[k]=None if f is None else {'id':f.id,'version':f.version_no,
            'content_sha256':digest({'group':f.fact_group,'value':f.value_json,'source_type':f.source_type,
                'source_ref':f.source_ref,'created_at':_utc(f.created_at).isoformat(),
                'expires_at':_utc(f.expires_at).isoformat() if f.expires_at else None})}
    return {'schema':'reviewed-evidence-approval-v1','customer_id':customer_id,'procurement_ref':plan.procurement_ref,
            'plan_approval_digest':approved_digest,'inputs_approval_digest':approved_inputs_digest,
            'latest_facts':versions,'fields':fields,'documentary_candidates':docs,'selected_documents':selected,
            'offer':offer,'declarations':declarations}


def _prepare(session,*,customer_id,root,run_id,approved_digest,approved_inputs_digest,
             templates,selections,signatory,goods_used,cost,offer_terms,declaration_terms,now):
    plan,_=_approved(customer_id=customer_id,run_id=run_id,signatory=signatory,goods_used=goods_used,
                     approved_digest=approved_digest)
    inputs={'approved_digest':approved_digest,'templates':templates,'selections':selections,'cost':cost,
            'offer_terms':offer_terms,'declaration_terms':declaration_terms}
    if bundle_inputs_digest(**inputs)!=approved_inputs_digest:
        raise ValueError('Exact bundle input approval required')
    return _snapshot(session,customer_id=customer_id,root=root,plan=plan,templates=templates,selections=selections,
        offer_terms=offer_terms,declaration_terms=declaration_terms,now=now,approved_digest=approved_digest,
        approved_inputs_digest=approved_inputs_digest)


def preview_evidence_approval(session,*,customer_id,root,run_id,approved_digest,approved_inputs_digest,
             templates,selections,signatory='UNKNOWN',goods_used=None,cost=None,offer_terms=None,declaration_terms=None,now=None):
    now=_utc(now or datetime.now(UTC))
    snapshot=_prepare(session,customer_id=customer_id,root=root,run_id=run_id,approved_digest=approved_digest,
        approved_inputs_digest=approved_inputs_digest,templates=templates,selections=selections,signatory=signatory,
        goods_used=goods_used,cost=cost,offer_terms=offer_terms,declaration_terms=declaration_terms,now=now)
    return {'status':'PRIVATE_EVIDENCE_REVIEW_ONLY','evidence_approval_digest':digest(snapshot),
            'projection':snapshot,'authenticated_approval':False,'application_ready':False}


def _verify_receipts(manifest,snapshot):
    rows={r['code']:r for r in manifest['items']}
    if {k for k,r in rows.items() if 'field_receipt' in r}!=set(snapshot['fields']):
        raise ValueError('Unexpected rendered identity receipt')
    if {k for k,r in rows.items() if 'selected_claim' in r}!=set(snapshot['selected_documents']):
        raise ValueError('Unexpected selected document receipt')
    for code,fields in snapshot['fields'].items():
        if rows[code].get('field_receipt',{}).get('fields')!=fields:
            raise ValueError('Rendered identity differs from approved evidence')
    for code,source in snapshot['selected_documents'].items():
        if rows[code].get('source')!=source:
            raise ValueError('Selected document differs from approved evidence')
    offer_receipts=[];declaration_receipts=[]
    for row in rows.values():
        if row['applicability']=='CONDITIONAL_UNKNOWN' and row['paths']:
            raise ValueError('Unresolved applicability produced output')
        if 'offer_receipt' in row:
            r=row['offer_receipt']
            offer_receipts.append({'subject_sha256':r['subject_sha256'],'source':r['source']})
        if 'declaration_receipt' in row:
            projection={r['code']:{'subject_sha256':r['subject_sha256'],'source':r['source']}
                        for r in row['declaration_receipt']['rows']}
            declaration_receipts.append(projection)
    if offer_receipts!=([snapshot['offer']] if snapshot['offer'] is not None else []):
        raise ValueError('Offer confirmation differs from approved evidence')
    if declaration_receipts!=([snapshot['declarations']] if snapshot['declarations'] else []):
        raise ValueError('Declaration confirmations differ from approved evidence')


def build_with_evidence_approval(session,*,approved_evidence_digest,customer_id,root,run_id,
                                approved_digest,approved_inputs_digest,templates,selections,
                                signatory='UNKNOWN',goods_used=None,cost=None,offer_terms=None,declaration_terms=None,now=None):
    now=_utc(now or datetime.now(UTC))
    args={'customer_id': customer_id,'root': root,'run_id': run_id,'approved_digest': approved_digest,
        'approved_inputs_digest': approved_inputs_digest,'templates': templates,'selections': selections,
        'signatory': signatory,'goods_used': goods_used,'cost': cost,'offer_terms': offer_terms,'declaration_terms': declaration_terms,'now': now}
    before=_prepare(session,**args)
    if digest(before)!=approved_evidence_digest:
        raise ValueError('Exact evidence version approval required')
    raw,out=build_from_checklist(session,**args)
    after=_prepare(session,**args)
    if after!=before:
        raise ValueError('Reviewed evidence changed during assembly')
    _verify_receipts(out['manifest'],before)
    if verify_private_review_bundle(raw,expected_sha256=out['archive_sha256'])!=out['manifest']:
        raise ValueError('Archive manifest differs from verified receipt')
    return raw,{**out,'evidence_approval_digest':approved_evidence_digest,
                'evidence_versions_match':True,'authenticated_approval':False,'application_ready':False}
