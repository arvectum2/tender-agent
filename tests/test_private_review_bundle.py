"""Independent synthetic private review ZIP with source-derived fields."""
import hashlib
import io
import json
import zipfile
from datetime import timedelta

import pytest
from docx import Document
from openpyxl import load_workbook
from test_qualification_readiness import NOW, add, fixture  # noqa: F401
from test_source_bound_form_fill import template

from src.modules.application_package_generator.private_review_bundle import (
    ReviewBundlePlan,
    build_private_review_bundle,
    verify_private_review_bundle,
)
from src.modules.company_profile_store.models import CompanyProfileFactVersion


def plan():
    d,dm=template('docx');x,xm=template('xlsx')
    p=ReviewBundlePlan(customer_id='owner',procurement_ref='synthetic-quotation',plan_review_ref='synthetic-reviewed-v1',
        owner_reviewed_plan=True,forms=[
            {'code':'quotation','source_ref':'fixture:form','template_map':dm},
            {'code':'cost_table','source_ref':'fixture:table','template_map':xm},
            {'code':'declaration','source_ref':'fixture:declaration'}],
        attachments=[
            {'code':'sme_proof','source_ref':'fixture:sme','applicability':'REQUIRED','alternatives':{'sme_membership':'sme'},'selected_claim':'sme_membership'},
            {'code':'rights','source_ref':'fixture:rights','applicability':'OPTIONAL_EVIDENCE','alternatives':{'right_letter':'rights','partner_certificate':'rights'}},
            {'code':'poa','source_ref':'fixture:poa','applicability':'CONDITIONAL_UNKNOWN','alternatives':{'power_of_attorney':'authority'}},
            {'code':'delegated_signer','source_ref':'fixture:delegate','applicability':'NOT_TRIGGERED','alternatives':{'delegated_signer_authority':'authority'}}],
        unresolved_requirement_codes=['other_tz_documents'],
        price_scenario={'external_direct_rub':'250000','labor_rub':'300000','reserve_rub':'50000','fixed_platform_fees_rub':'10000',
                        'revenue_tax_percent':'6','variable_platform_fee_percent':'1','target_profit_rub':'100000',
                        'accept_hypothetical_assumptions_only':True,'offer_scenario':{'offer_price_rub':'900000',
                        'nonrefundable_guarantee_fees_rub':'5000','refundable_bid_cash_rub':'20000','refundable_contract_cash_rub':'100000'}})
    return p,{'quotation':d,'cost_table':x}


def identity(s):
    s.add(CompanyProfileFactVersion(customer_id='owner',fact_key='draft_identity:legal_name',fact_group='IDENTITY',
        version_no=1,value_json={'schema_version':'draft-identity-value-v1','inn':'1234567890','field_code':'legal_name',
                                 'value':'owner','observed_on':'2026-11-18','owner_confirmed':True},
        source_type='OWNER_CONFIRMED',source_ref='synthetic-owner-review',expires_at=NOW+timedelta(days=30),created_at=NOW))
    s.commit()


def build(s,root,p,t,**kwargs):
    args={'customer_id':'owner','procurement_ref':'synthetic-quotation','root':root,'plan':p,'templates':t,'now':NOW}
    return build_private_review_bundle(s,**(args|kwargs))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def test_complete_review_archive_roundtrip(fixture):  # noqa: F811
    s,root,pdf,claim,_=fixture
    identity(s);add(s,claim)
    p,t=plan();before={k:sha(v) for k,v in t.items()}
    raw,r=build(s,root,p,t)
    assert r['archive_sha256']==sha(raw)
    assert r['status']=='PRIVATE_REVIEW_ONLY' and not r['application_ready']
    verified=verify_private_review_bundle(raw,expected_sha256=r['archive_sha256'],customer_id='owner',procurement_ref=p.procurement_ref)
    assert verified['status']=='INTEGRITY_MATCH_ONLY' and verified['file_count']==r['file_count']
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert z.testzip() is None
        assert z.read('candidate_attachments/sme_proof.pdf')==pdf.read_bytes()
        d=Document(io.BytesIO(z.read('draft_forms/quotation.docx')))
        assert 'owner' in d.paragraphs[0].text and '{{INN}}' in d.paragraphs[1].text
        x=load_workbook(io.BytesIO(z.read('draft_forms/cost_table.xlsx')))
        assert x['Form']['A1'].value=='owner' and x['Form']['A2'].value=='{{INN}}'
        assert x['Form']['B1'].value=='=SUM(1,2)'
        m=json.loads(z.read('internal_review/inventory.json'))
        assert len(z.namelist())==len(m['inventory'])+1==r['file_count']==9
        assert sha(z.read('internal_review/inventory.json'))==r['inventory_sha256']
        for row in m['inventory']:
            assert sha(z.read(row['path']))==row['sha256']
        gaps=json.loads(z.read('internal_review/gaps.json'))
        assert r['gap_count']==len(gaps)==10
        assert any(g['reason']=='EXPLICIT_CHOICE_REQUIRED' and len(g['alternatives'])==2 for g in gaps)
        assert any(g['code']=='poa' and g['reason']=='APPLICABILITY_UNKNOWN' for g in gaps)
        assert not any(g['code']=='delegated_signer' for g in gaps)
        price=json.loads(z.read('internal_review/price_scenario.json'))
        assert price['offer_scenario']['economic_profit_rub']=='222000.00' and not price['commercial_owner_go']
        assert not m['commercial_price_approved'] and not m['submission_performed']
    assert before=={k:sha(v) for k,v in t.items()}


@pytest.mark.parametrize('change',['missing','negative','expired','tamper','foreign'])
def test_candidate_never_included_unconfirmed(fixture,change):  # noqa: F811
    s,root,pdf,claim,_=fixture
    p,t=plan()
    if change=='negative':add(s,claim|{'assertion':'ABSENT'})
    elif change=='expired':add(s,claim,expires=NOW)
    elif change=='tamper':
        add(s,claim);pdf.write_bytes(b'%PDF-1.4\nchanged')
    elif change=='foreign':
        add(s,claim|{'inn':'0987654321'})
    raw,_=build(s,root,p,t)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert not any(n.startswith('candidate_attachments/') for n in z.namelist())
        assert any(g['code']=='sme_proof' and g['reason']=='CANDIDATE_MISSING_OR_UNCONFIRMED' for g in json.loads(z.read('internal_review/gaps.json')))


@pytest.mark.parametrize('change',['wrong_scope','wrong_procurement','unreviewed','extra_template','changed_template','bad_choice','duplicate_code'])
def test_plan_or_template_rejected(fixture,change):  # noqa: F811
    s,root,_,_,_=fixture;p,t=plan();d=p.model_dump();opts={}
    if change=='wrong_scope':opts['customer_id']='other'
    elif change=='wrong_procurement':opts['procurement_ref']='elsewhere'
    elif change=='unreviewed':d['owner_reviewed_plan']=False
    elif change=='extra_template':t['foreign']=b'not allowed'
    elif change=='changed_template':t['quotation']+=b'!'
    elif change=='bad_choice':d['attachments'][1]['selected_claim']='foreign'
    elif change=='duplicate_code':d['forms'][1]['code']='quotation'
    with pytest.raises(ValueError):
        build(s,root,ReviewBundlePlan.model_validate(d),t,**opts)


def test_integrity_refuses_change_or_scope(fixture):  # noqa: F811
    s,root,_,_,_=fixture;p,t=plan()
    raw,r=build(s,root,p,t)
    with pytest.raises(ValueError):
        verify_private_review_bundle(raw+b'!',expected_sha256=r['archive_sha256'],customer_id='owner',procurement_ref=p.procurement_ref)
    with pytest.raises(ValueError):
        verify_private_review_bundle(raw,expected_sha256=r['archive_sha256'],customer_id='other',procurement_ref=p.procurement_ref)
    changed=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as src,zipfile.ZipFile(changed,'w') as dst:
        for name in src.namelist():
            dst.writestr(name,src.read(name)+(b'!' if name=='README_REVIEW_ONLY.txt' else b''))
    altered=changed.getvalue()
    with pytest.raises(ValueError,match='member digest'):
        verify_private_review_bundle(altered,expected_sha256=sha(altered),customer_id='owner',procurement_ref=p.procurement_ref)


@pytest.mark.parametrize('change',['positive_flag','extra_member','foreign_plan'])
def test_invalid_inventory_envelope(fixture,change):  # noqa: F811
    s,root,_,_,_=fixture;p,t=plan();raw,_=build(s,root,p,t)
    out=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        files={n:z.read(n) for n in z.namelist()}
    key='internal_review/inventory.json'
    manifest=json.loads(files[key])
    if change=='positive_flag':
        manifest['application_ready']=True
    elif change=='extra_member':
        files['extra.txt']=b'extra'
    elif change=='foreign_plan':
        key_plan='internal_review/reviewed_plan.json'
        foreign=json.loads(files[key_plan]);foreign['customer_id']='other'
        files[key_plan]=json.dumps(foreign).encode()
        manifest['plan_sha256']=sha(files[key_plan])
        for row in manifest['inventory']:
            if row['path']==key_plan:
                row.update(sha256=sha(files[key_plan]),size_bytes=len(files[key_plan]))
    files[key]=json.dumps(manifest).encode()
    with zipfile.ZipFile(out,'w') as z:
        for n,v in files.items():z.writestr(n,v)
    changed=out.getvalue()
    with pytest.raises(ValueError):
        verify_private_review_bundle(changed,expected_sha256=sha(changed),customer_id='owner',procurement_ref=p.procurement_ref)
