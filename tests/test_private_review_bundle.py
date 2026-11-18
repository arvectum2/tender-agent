# ruff: noqa: F811

"""Independent synthetic bundle round trip; no real corporate packet."""
import io
import json
import zipfile

import pytest
from docx import Document
from openpyxl import load_workbook
from test_operator_cashflow_calendar import cost
from test_qualification_readiness import NOW, add, fixture  # noqa: F401
from test_source_bound_form_fill import fact, template

from src.modules.application_package_generator.private_review_bundle import (
    ReviewPlan,
    build_private_review_bundle,
    verify_private_review_bundle,
)


def plan():
    rows=[
        ('bid','FORM','REQUIRED',{}),
        ('spec','FORM','REQUIRED',{}),
        ('sme','DOCUMENT','REQUIRED',{'sme_membership':'sme'}),
        ('rights','ALTERNATIVES','OPTIONAL_EVIDENCE',{'letter':'rights','certificate':'rights'}),
        ('poa','DOCUMENT','NOT_TRIGGERED',{'power_of_attorney':'authority'}),
        ('declarations','DECLARATION','REQUIRED',{}),
        ('price','PRICE','REQUIRED',{}),
        ('other','CROSS_REFERENCE','CONDITIONAL_UNKNOWN',{}),
    ]
    return ReviewPlan(procurement_ref='synthetic-quotation',plan_review_ref='fixture-reviewed-v1',owner_reviewed_plan=True,
        items=[{'code':k,'role':r,'applicability':a,'review_ref':'synthetic:'+k,'claims':c} for k,r,a,c in rows])


def build(fixture,**kwargs):
    s,root,_,_,_=fixture
    options={'customer_id':'owner','root':root,'plan':plan(),'templates':{'bid':template('docx'),'spec':template('xlsx')},
             'selections':{'sme':'sme_membership'},'cost':cost(),'now':NOW}
    options.update(kwargs)
    return build_private_review_bundle(s,**options)


def test_private_bundle_roundtrip(fixture):
    s,_,p,claim,_=fixture
    add(s,claim)
    fact(s,'legal_name','owner',customer='owner')
    before=p.read_bytes()
    raw,m=build(fixture)
    assert verify_private_review_bundle(raw)==m
    assert len(m['inventory'])==4
    assert len(m['unresolved_item_codes'])==7
    assert all(not m[k] for k in ('application_ready','go_eligible','signed','submitted','external_delivery'))
    rows={r['code']:r for r in m['items']}
    assert rows['bid']['field_receipt']['filled_count']==1
    assert rows['bid']['field_receipt']['unknown_count']==1
    assert rows['sme']['state']=='CANDIDATE_REVIEW_REQUIRED'
    assert rows['rights']['state']=='MISSING_OR_REVIEW_REQUIRED'
    assert rows['poa']['paths']==[] and rows['declarations']['paths']==[]
    assert all(r['satisfied'] is None for r in rows.values())
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert z.read('evidence/sme.pdf')==before==p.read_bytes()
        d=Document(io.BytesIO(z.read('forms/bid.docx')))
        assert d.paragraphs[0].runs[1].text=='owner' and '{{INN}}' in d.paragraphs[1].text
        w=load_workbook(io.BytesIO(z.read('forms/spec.xlsx')))['Form']
        assert w['A1'].value=='owner' and w['A2'].value=='{{INN}}' and w['B1'].value=='=SUM(1,2)'
        assert json.loads(z.read('internal/price-scenario.json'))['status']=='HYPOTHETICAL_PRICE_NOT_OFFER'


@pytest.mark.parametrize('change',['missing','negative','tampered','foreign','wrong_selection','unexpected_template','unreviewed','duplicate','nontriggered'])
def test_fail_closed(fixture,change):
    s,_,p,claim,_=fixture
    if change!='missing':
        add(s,{**claim,'assertion':'ABSENT' if change=='negative' else 'PRESENT'})
    opts={}
    if change=='tampered':p.write_bytes(b'%PDF-1.4\nchanged')
    elif change=='foreign':opts['customer_id']='other'
    elif change=='wrong_selection':opts['selections']={'sme':'certificate'}
    elif change=='unexpected_template':opts['templates']={'other':template('docx')}
    elif change=='unreviewed':opts['plan']=plan().model_copy(update={'owner_reviewed_plan':False})
    elif change=='duplicate':
        q=plan();opts['plan']=q.model_copy(update={'items':[ *q.items,q.items[0]]})
    elif change=='nontriggered':opts['selections']={'poa':'power_of_attorney'}
    with pytest.raises(ValueError):
        build(fixture,**opts)


def test_alternatives_never_auto_selected(fixture):
    s,_,_,claim,_=fixture
    add(s,{**claim,'requirement_code':'letter'},key='qualification_claim:letter')
    _,m=build(fixture,selections={})
    assert not any(x['role']=='DOCUMENTARY_CANDIDATE' for x in m['inventory'])
    raw,m=build(fixture,selections={'rights':'letter'})
    assert [x['path'] for x in m['inventory'] if x['role']=='DOCUMENTARY_CANDIDATE']==['evidence/rights.pdf']
    assert verify_private_review_bundle(raw)==m


@pytest.mark.parametrize('change',['bytes','extra','ready','gap','row'])
def test_archive_integrity(fixture,change):
    raw,_=build(fixture,selections={})
    out=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as a,zipfile.ZipFile(out,'w') as b:
        for path in a.namelist():
            data=a.read(path)
            if change=='bytes' and path=='forms/bid.docx':data+=b'altered'
            if path=='manifest.json':
                m=json.loads(data)
                if change=='ready':m['application_ready']=True
                elif change=='gap':m['unresolved_item_codes']=[]
                elif change=='row':m['items'][0]['paths']=[]
                data=json.dumps(m).encode()
            b.writestr(path,data)
        if change=='extra':b.writestr('source-notice.pdf',b'foreign')
    with pytest.raises(ValueError):
        verify_private_review_bundle(out.getvalue())


def test_external_digest_and_cross_form_facts(fixture,monkeypatch):
    import hashlib

    from src.modules.application_package_generator import (
        private_review_bundle as bundle,
    )

    raw,_=build(fixture,selections={})
    assert verify_private_review_bundle(raw,expected_sha256=hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError,match='external digest'):
        verify_private_review_bundle(raw,expected_sha256='0'*64)
    real=bundle._resolve
    def changed(*args,**kwargs):
        fields=real(*args,**kwargs)
        fields[0]['state']='CHANGED'
        return fields
    monkeypatch.setattr(bundle,'_resolve',changed)
    with pytest.raises(ValueError,match='Identity facts changed'):
        build(fixture,selections={})
