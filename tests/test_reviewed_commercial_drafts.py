"""Synthetic owner confirmation and real draft DOCX/ZIP round trips."""
import io
import zipfile
from datetime import timedelta

import pytest
from docx import Document
from test_operator_cashflow_calendar import cost
from test_private_review_bundle import build
from test_qualification_readiness import NOW, add, fixture  # noqa: F401

from src.modules.application_package_generator.reviewed_commercial_drafts import (
    DeclarationTerms,
    OfferTerms,
    render_declarations,
    render_offer,
    subject_digest,
)
from src.modules.company_profile_store.models import CompanyProfileFactVersion

# ruff: noqa: F811


def offer():
    return OfferTerms(procurement_ref='synthetic-quotation',lot_ref='lot1',
        reviewed_source_ref='synthetic-reviewed-tz',lines=[
            {'description':'Synthetic service A','quantity':'2','unit':'шт.','gross_unit_price_rub':'300000'},
            {'description':'Synthetic service B','quantity':'1','unit':'шт.','gross_unit_price_rub':'300000'}],
        total_rub='900000',ceiling_rub='1000000',vat_mode='WITHOUT_VAT_EXPLICIT',
        vat_amount_rub='0',vat_basis='Synthetic tax assumption',valid_through='2026-12-01')


def declarations():
    return DeclarationTerms(procurement_ref='synthetic-quotation',statements=[
        {'code':'statement_a','exact_wording':'Synthetic confirmed statement A','reviewed_source_ref':'fixture-a'},
        {'code':'statement_b','exact_wording':'Synthetic unsupported statement B','reviewed_source_ref':'fixture-b'}])


def assertion(s,key,subject,*,version=1,customer_id='owner',**overrides):
    value={'schema_version':'commercial-draft-assertion-v1','inn':'1234567890',
           'procurement_ref':subject.procurement_ref,'subject_sha256':subject_digest(subject),
           'observed_on':'2026-11-18','owner_confirmed':True,'assertion':'CONFIRMED',**overrides}
    f=CompanyProfileFactVersion(customer_id=customer_id,fact_key=key,fact_group='OTHER',version_no=version,
        value_json=value,source_type='OWNER_CONFIRMED',source_ref='synthetic-owner-review',
        expires_at=NOW+timedelta(days=10),created_at=NOW)
    s.add(f);s.commit();return f.id


def render(s,o=None,cid='owner'):
    return render_offer(s,customer_id=cid,terms=o or offer(),cost=cost(),now=NOW)


def test_offer_confirmation_and_output(fixture):
    s,*_=fixture
    raw,r=render(s)
    assert raw is None and r['status']=='OFFER_CONFIRMATION_MISSING'
    fid=assertion(s,'draft_offer:synthetic-quotation',offer())
    raw,r=render(s)
    assert r['source']['fact_id']==fid
    doc=Document(io.BytesIO(raw))
    assert doc.tables[0].rows[1].cells[-1].text=='600000.00'
    assert doc.tables[0].rows[2].cells[-1].text=='300000.00'
    text='\n'.join(p.text for p in doc.paragraphs)
    assert '900000.00' in text and 'Без НДС' in text and 'НЕ ПОДПИСАНО' in text
    assert '222000' not in text and '678000' not in text and 'synthetic-owner-review' not in text
    assert not r['application_ready'] and not r['signed']
    assert render(s,cid='other')[0] is None


@pytest.mark.parametrize('change',['total_rub','ceiling_rub','vat_amount_rub','valid_through','vat_rate_percent'])
def test_inconsistent_offer_refused(fixture,change):
    s,*_=fixture
    values={'total_rub':'899999','ceiling_rub':'899999','vat_amount_rub':'1',
            'valid_through':'2026-11-17','vat_rate_percent':'20'}
    d=offer().model_dump();d[change]=values[change]
    with pytest.raises(ValueError):
        render(s,OfferTerms.model_validate(d))


def test_vat_gross_arithmetic(fixture):
    s,*_=fixture
    d=offer().model_dump()
    d.update(vat_mode='VAT_EXPLICIT',vat_rate_percent='20',vat_amount_rub='150000')
    o=OfferTerms.model_validate(d)
    assertion(s,'draft_offer:synthetic-quotation',o)
    raw,_=render(s,o)
    assert '150000.00' in '\n'.join(p.text for p in Document(io.BytesIO(raw)).paragraphs)


@pytest.mark.parametrize('change',['inn','procurement_ref','subject_sha256','observed_on','owner_confirmed','assertion'])
def test_latest_claim_no_fallback(fixture,change):
    s,*_=fixture
    o=offer();key='draft_offer:synthetic-quotation'
    assertion(s,key,o)
    bad={'inn':'0987654321','procurement_ref':'other','subject_sha256':'0'*64,
         'observed_on':'2026-10-01','owner_confirmed':False,'assertion':'NOT_CONFIRMED'}
    assertion(s,key,o,version=2,**{change:bad[change]})
    assert render(s)[0] is None


def test_exact_declaration_and_unknown(fixture):
    s,*_=fixture
    terms=declarations()
    key='draft_declaration:statement_a'
    one=DeclarationTerms(procurement_ref=terms.procurement_ref,statements=terms.statements[:1])
    assertion(s,key,one)
    raw,r=render_declarations(s,customer_id='owner',terms=terms,now=NOW)
    text='\n'.join(p.text for p in Document(io.BytesIO(raw)).paragraphs)
    assert 'Synthetic confirmed statement A' in text and 'Synthetic unsupported statement B' not in text
    assert r['unanswered_count']==1
    changed=terms.model_dump();changed['statements'][0]['exact_wording']+=' changed'
    _,r=render_declarations(s,customer_id='owner',terms=DeclarationTerms.model_validate(changed),now=NOW)
    assert r['unanswered_count']==2


def test_integrated_bundle(fixture):
    s,_,_,claim,_=fixture
    add(s,claim)
    o=offer();d=declarations()
    assertion(s,'draft_offer:synthetic-quotation',o)
    assertion(s,'draft_declaration:statement_a',DeclarationTerms(procurement_ref=d.procurement_ref,statements=d.statements[:1]))
    raw,m=build(fixture,offer_terms=o,declaration_terms=d)
    assert len(m['inventory'])==6 and not m['application_ready']
    rows={r['code']:r for r in m['items']}
    assert rows['price']['offer_receipt']['source']
    assert rows['declarations']['declaration_receipt']['unanswered_count']==1
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert 'drafts/price-offer.docx' in z.namelist()
        assert 'drafts/declarations.docx' in z.namelist()
        assert 'internal/price-scenario.json' in z.namelist()
    with pytest.raises(ValueError):
        build(fixture,offer_terms=o.model_copy(update={'procurement_ref':'foreign'}))


def test_price_must_match_scenario(fixture):
    s,*_=fixture
    c=cost()
    c.offer_scenario.offer_price_rub='899999'
    with pytest.raises(ValueError,match='PRICE01'):
        render_offer(s,customer_id='owner',terms=offer(),cost=c,now=NOW)


def test_bundle_missing_confirmations_remain_open(fixture):
    raw,m=build(fixture,offer_terms=offer(),declaration_terms=declarations(),selections={})
    rows={r['code']:r for r in m['items']}
    assert rows['price']['state']=='OFFER_CONFIRMATION_MISSING'
    assert rows['declarations']['declaration_receipt']['unanswered_count']==2
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert 'drafts/price-offer.docx' not in z.namelist()
        assert 'drafts/declarations.docx' in z.namelist()
    assert 'price' in m['unresolved_item_codes'] and 'declarations' in m['unresolved_item_codes']
