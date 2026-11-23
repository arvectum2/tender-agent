"""Synthetic evidence version pinning for consolidated source-derived bundle."""
import io
import zipfile
from datetime import timedelta

import pytest
from docx import Document
from test_checklist_bundle_gate import observed, preview  # noqa: F401
from test_operator_cashflow_calendar import cost
from test_qualification_readiness import NOW, add, fixture  # noqa: F401
from test_reviewed_commercial_drafts import assertion, declarations, offer
from test_source_bound_form_fill import fact, template

from src.modules.application_package_generator import evidence_approval_gate as gate
from src.modules.application_package_generator.checklist_bundle_gate import (
    bundle_inputs_digest,
)
from src.modules.application_package_generator.reviewed_commercial_drafts import (
    DeclarationTerms,
)

# ruff: noqa: F811


def inputs(fixture,*,signatory='DIRECTOR',goods=False,selection=True):
    s,root,_,claim,_=fixture
    fact(s,'legal_name','owner',customer='owner')
    add(s,{**claim,'requirement_code':'director_appointment'},key='qualification_claim:director_appointment',group='IDENTITY')
    o=offer().model_copy(update={'procurement_ref':'32616444788'})
    d=declarations().model_copy(update={'procurement_ref':'32616444788'})
    assertion(s,'draft_offer:32616444788',o)
    assertion(s,'draft_declaration:statement_a',DeclarationTerms(procurement_ref=d.procurement_ref,statements=d.statements[:1]))
    p=preview(signatory=signatory,goods_used=goods)
    args={'customer_id':'owner','root':root,'run_id':'fixture','approved_digest':p['approval_digest'],
          'templates':{'application_form':template('docx')},
          'selections':{'director_appointment':'director_appointment'} if selection else {},
          'signatory':signatory,'goods_used':goods,'cost':cost(),'offer_terms':o,'declaration_terms':d,'now':NOW}
    approve_inputs(args)
    return args


def approve_inputs(args):
    args['approved_inputs_digest']=bundle_inputs_digest(**{k:args[k] for k in
        ('approved_digest','templates','selections','cost','offer_terms','declaration_terms')})


def approve(s,args):
    return gate.preview_evidence_approval(s,**args)['evidence_approval_digest']


def test_exact_evidence_roundtrip(fixture,observed):
    s,*_=fixture;args=inputs(fixture)
    p=gate.preview_evidence_approval(s,**args)
    raw,out=gate.build_with_evidence_approval(s,approved_evidence_digest=p['evidence_approval_digest'],**args)
    assert out['evidence_versions_match'] and not out['authenticated_approval'] and not out['application_ready']
    assert p['projection']['latest_facts']['draft_identity:inn'] is None
    assert p['projection']['declarations']['statement_b']['source'] is None
    assert out['coverage_review']['open_item_count']==7
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        d=Document(io.BytesIO(z.read('drafts/price-offer.docx')))
        text=' '.join(p.text for p in d.paragraphs)
        assert '900000.00' in text and '222000' not in text
        assert 'evidence/director_appointment.pdf' in z.namelist()
        assert 'drafts/declarations.docx' in z.namelist()


@pytest.mark.parametrize('change',['identity','missing_identity','document','offer','declaration','unanswered','expiry'])
def test_latest_change_requires_new_approval(fixture,observed,change):
    s,_,_,claim,_=fixture;args=inputs(fixture);sha=approve(s,args)
    if change=='identity':fact(s,'legal_name','owner',customer='owner',version=2)
    elif change=='missing_identity':fact(s,'inn','1234567890',customer='owner')
    elif change=='document':add(s,{**claim,'requirement_code':'director_appointment'},key='qualification_claim:director_appointment',group='IDENTITY',version=2)
    elif change=='offer':assertion(s,'draft_offer:32616444788',args['offer_terms'],version=2)
    elif change=='declaration':assertion(s,'draft_declaration:statement_a',DeclarationTerms(procurement_ref='32616444788',statements=args['declaration_terms'].statements[:1]),version=2)
    elif change=='unanswered':assertion(s,'draft_declaration:statement_b',DeclarationTerms(procurement_ref='32616444788',statements=args['declaration_terms'].statements[1:]))
    elif change=='expiry':args['now']=NOW+timedelta(days=11)
    assert approve(s,args)!=sha
    with pytest.raises(ValueError,match='evidence version approval'):
        gate.build_with_evidence_approval(s,approved_evidence_digest=sha,**args)


def test_tampered_selected_file_refused(fixture,observed):
    s,_,pdf,_,_=fixture;args=inputs(fixture);sha=approve(s,args)
    pdf.write_bytes(b'%PDF-1.4\nchanged')
    with pytest.raises(ValueError,match='candidate unavailable'):
        gate.build_with_evidence_approval(s,approved_evidence_digest=sha,**args)


def test_unknown_condition_not_permission(fixture,observed):
    s,*_=fixture;args=inputs(fixture,signatory='UNKNOWN',goods=None)
    args['templates']['goods_description']=template('xlsx');approve_inputs(args)
    with pytest.raises(ValueError,match='Unresolved'):
        approve(s,args)


def test_change_during_assembly(fixture,observed,monkeypatch):
    s,*_=fixture;args=inputs(fixture);sha=approve(s,args)
    original=gate.build_from_checklist
    def build(*a,**kw):
        out=original(*a,**kw)
        fact(s,'legal_name','owner',customer='owner',version=2)
        return out
    monkeypatch.setattr(gate,'build_from_checklist',build)
    with pytest.raises(ValueError,match='changed during assembly'):
        gate.build_with_evidence_approval(s,approved_evidence_digest=sha,**args)


def test_receipt_mismatch_refused(fixture,observed,monkeypatch):
    s,*_=fixture;args=inputs(fixture);sha=approve(s,args)
    original=gate.build_from_checklist
    def build(*a,**kw):
        raw,out=original(*a,**kw)
        row=next(r for r in out['manifest']['items'] if r['code']=='price_component')
        row['offer_receipt']['source']=None
        return raw,out
    monkeypatch.setattr(gate,'build_from_checklist',build)
    with pytest.raises(ValueError,match='Offer confirmation'):
        gate.build_with_evidence_approval(s,approved_evidence_digest=sha,**args)


def test_archive_bytes_must_match_receipt(fixture,observed,monkeypatch):
    s,*_=fixture;args=inputs(fixture);sha=approve(s,args)
    original=gate.build_from_checklist
    def build(*a,**kw):
        raw,out=original(*a,**kw)
        return raw+b'changed',out
    monkeypatch.setattr(gate,'build_from_checklist',build)
    with pytest.raises(ValueError,match='pinned external digest'):
        gate.build_with_evidence_approval(s,approved_evidence_digest=sha,**args)


def test_unknown_document_not_permission(fixture,observed):
    s,*_=fixture;args=inputs(fixture,signatory='UNKNOWN',goods=None)
    args['selections']['power_of_attorney']='power_of_attorney';approve_inputs(args)
    with pytest.raises(ValueError,match='Unresolved'):
        approve(s,args)


def test_pending_profile_edit_refused(fixture,observed):
    from sqlalchemy import select

    from src.modules.customer_registry.models import CustomerProfile
    s,*_=fixture;args=inputs(fixture)
    profile=s.scalar(select(CustomerProfile).where(CustomerProfile.customer_id=='owner'))
    profile.legal_name='uncommitted change'
    with pytest.raises(ValueError,match='clean session'):
        approve(s,args)
    s.rollback()
