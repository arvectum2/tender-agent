# ruff: noqa: F811
"""Synthetic source receipts, no real archive access or private original replay."""
import hashlib
import io
import json
import zipfile

import pytest
from test_operator_cashflow_calendar import cost
from test_qualification_readiness import NOW, fixture  # noqa: F401
from test_source_bound_form_fill import fact, template

from src.modules.application_package_generator import checklist_bundle_gate as gate
from src.modules.application_package_generator.private_review_bundle import ReviewPlan
from src.modules.tender_operator_agent_demo.ri223_application_source import (
    SOURCE_PARAGRAPHS,
)


def packet():
    return {'status':'ARCHIVED_QUOTATION_CHECKLIST_REVIEW_ONLY','procurement_number':'32616444788',
            'source_groups':{sha:{k:[{'quote':q,'original_sha256':sha,'file_id':f'fixture-{i}',
                'chunk_id':f'fixture-{i}-{k}'}] for k,q in groups.items()}
                for i,(sha,groups) in enumerate(SOURCE_PARAGRAPHS.items())}}


@pytest.fixture
def observed(monkeypatch):
    p=packet()
    monkeypatch.setattr(gate,'observe_application',lambda _:p)
    return p


def preview(**kwargs):
    return gate.preview_plan(**{'customer_id':'owner','run_id':'fixture','signatory':'DIRECTOR','goods_used':False,**kwargs})


def build(fixture,**kwargs):
    s,root,*_=fixture
    p=preview()
    args={'customer_id':'owner','root':root,'run_id':'fixture','approved_digest':p['approval_digest'],
          'templates':{'application_form':template('docx')},'selections':{},'signatory':'DIRECTOR',
          'goods_used':False,'cost':cost(),'now':NOW}
    return gate.build_from_checklist(s,**{**args,**kwargs})


def test_full_projection_and_gap_report(fixture,observed):
    s,*_=fixture
    fact(s,'legal_name','owner',customer='owner')
    p=preview()
    assert not p['plan']['owner_reviewed_plan']
    raw,out=build(fixture)
    review=out['coverage_review']
    assert review['reviewed_source_row_count']==9 and review['plan_item_count']==10
    assert review['open_item_count']==7 and not review['application_ready']
    assert hashlib.sha256(raw).hexdigest()==out['archive_sha256']
    rows={r['code']:r for r in review['items']}
    assert 'UNKNOWN_IDENTITY_FIELDS' in rows['application_form']['reasons']
    assert 'DOCUMENTARY_CANDIDATE_MISSING' in rows['director_appointment']['reasons']
    assert 'OFFER_MISSING_OR_UNCONFIRMED' in rows['price_component']['reasons']
    assert 'DECLARATIONS_MISSING' in rows['declarations']['reasons']
    assert rows['power_of_attorney']['reasons']==[]
    assert rows['price_component']['derived_from']=='application_form'
    assert out['plan_approval_digest']==p['approval_digest']
    assert not review['current_facts_reattested'] and review['recommendation']=='DEFER'


@pytest.mark.parametrize('status',['UNKNOWN','ARCHIVED_NOTIFICATION_NOT_APPLICATION','INCOMPLETE_REVIEWED_SOURCE'])
def test_refuse_nonquotation(observed,status):
    observed['status']=status
    with pytest.raises(ValueError):
        preview()


@pytest.mark.parametrize('change',['paragraph','quote','sha','file','chunk'])
def test_source_lineage(observed,change):
    groups=next(iter(observed['source_groups'].values()))
    k=next(iter(groups))
    if change=='paragraph':
        groups.pop(k)
    else:
        field={'quote':'quote','sha':'original_sha256','file':'file_id','chunk':'chunk_id'}[change]
        groups[k][0][field]='' if change!='file' else 'foreign'
    with pytest.raises(ValueError):
        preview()


@pytest.mark.parametrize('change',['customer_id','run_id','signatory','goods_used'])
def test_approval_binds_scope(observed,change):
    values={'customer_id':'other','run_id':'other','signatory':'REPRESENTATIVE','goods_used':True}
    assert preview()['approval_digest']!=preview(**{change:values[change]})['approval_digest']


def test_wrong_approval_refused(fixture,observed):
    with pytest.raises(ValueError,match='approval'):
        build(fixture,approved_digest='0'*64)


def test_changed_source_after_build(fixture,observed,monkeypatch):
    import copy
    changed=copy.deepcopy(observed)
    next(iter(next(iter(changed['source_groups'].values())).values()))[0]['chunk_id']='new-chunk'
    calls=iter([observed,observed,changed])
    monkeypatch.setattr(gate,'observe_application',lambda _:next(calls))
    with pytest.raises(ValueError,match='approval'):
        build(fixture)


def rewrite(raw,mutator):
    out=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as a,zipfile.ZipFile(out,'w') as b:
        for name in a.namelist():
            data=a.read(name)
            if name=='manifest.json':
                m=json.loads(data);mutator(m);data=json.dumps(m).encode()
            b.writestr(name,data)
    return out.getvalue()


@pytest.mark.parametrize('change',['omitted','excluded','role','scope','receipt','digest'])
def test_independent_gate_rejects_consistent_but_wrong_manifest(fixture,observed,change):
    p=preview()
    raw,out=build(fixture)
    plan=ReviewPlan.model_validate({**p['plan'],'owner_reviewed_plan':True})
    def mutate(m):
        rows={r['code']:r for r in m['items']}
        if change=='omitted':
            m['items'].remove(rows['director_appointment'])
            m['unresolved_item_codes'].remove('director_appointment')
        elif change=='excluded':
            rows['director_appointment']['state']='NOT_TRIGGERED_IN_SCENARIO'
            m['unresolved_item_codes'].remove('director_appointment')
        elif change=='role':
            rows['director_appointment']['role']='CROSS_REFERENCE'
        elif change=='scope':
            m['customer_id']='other'
        elif change=='receipt':
            rows['application_form']['field_receipt']['unknown_count']=0
    altered=rewrite(raw,mutate)
    sha=out['archive_sha256'] if change=='digest' else hashlib.sha256(altered).hexdigest()
    with pytest.raises(ValueError):
        gate.assess_coverage(altered,expected_sha256=sha,plan=plan,scope=p['scope'])


def test_integrated_offer_declaration_and_document(fixture,observed):
    from test_qualification_readiness import add
    from test_reviewed_commercial_drafts import assertion, declarations, offer

    from src.modules.application_package_generator.reviewed_commercial_drafts import (
        DeclarationTerms,
    )

    s,_,_,claim,doc=fixture
    fact(s,'legal_name','owner',customer='owner')
    add(s,{**claim,'requirement_code':'director_appointment'},key='qualification_claim:director_appointment',group='IDENTITY')
    assert doc.document_type=='STATUTORY'
    o=offer().model_copy(update={'procurement_ref':'32616444788'})
    d=declarations().model_copy(update={'procurement_ref':'32616444788'})
    assertion(s,'draft_offer:32616444788',o)
    assertion(s,'draft_declaration:statement_a',DeclarationTerms(procurement_ref=d.procurement_ref,statements=d.statements[:1]))
    raw,out=build(fixture,offer_terms=o,declaration_terms=d,selections={'director_appointment':'director_appointment'})
    rows={r['code']:r for r in out['coverage_review']['items']}
    assert rows['director_appointment']['output_count']==1
    assert 'DOCUMENT_SEMANTICS_UNVERIFIED' in rows['director_appointment']['reasons']
    assert rows['price_component']['output_count']==2
    assert 'OFFER_MISSING_OR_UNCONFIRMED' not in rows['price_component']['reasons']
    assert 'UNANSWERED_DECLARATIONS' in rows['declarations']['reasons']
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert set(z.namelist())=={'forms/application_form.docx','evidence/director_appointment.pdf',
                  'drafts/price-offer.docx','drafts/declarations.docx','internal/price-scenario.json','manifest.json'}
    assert out['coverage_review']['recommendation']=='DEFER'


def test_output_path_role_mismatch(fixture,observed):
    p=preview();raw,_=build(fixture)
    plan=ReviewPlan.model_validate({**p['plan'],'owner_reviewed_plan':True})
    out=io.BytesIO()
    old='forms/application_form.docx';new='forms/other.docx'
    with zipfile.ZipFile(io.BytesIO(raw)) as a,zipfile.ZipFile(out,'w') as b:
        for name in a.namelist():
            data=a.read(name)
            if name=='manifest.json':
                m=json.loads(data)
                next(r for r in m['items'] if r['code']=='application_form')['paths']=[new]
                next(r for r in m['inventory'] if r['path']==old)['path']=new
                data=json.dumps(m).encode()
            b.writestr(new if name==old else name,data)
    altered=out.getvalue()
    with pytest.raises(ValueError,match='path'):
        gate.assess_coverage(altered,expected_sha256=hashlib.sha256(altered).hexdigest(),plan=plan,scope=p['scope'])
