"""Authenticated synthetic HTTP/SQLite, no live company data."""
import base64
import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import select
from test_apr05_saas_foundation import _auth, _legal, _seed, enabled  # noqa: F401
from test_checklist_bundle_gate import packet
from test_source_bound_form_fill import template

from src.modules.application_package_generator import checklist_bundle_gate
from src.modules.saas_foundation import application_review, router
from src.modules.saas_foundation.models import (
    ApplicationReviewDecision,
    ApplicationReviewPreview,
    SaasMember,
    SaasRun,
)
from src.shared.config.settings import Settings


@pytest.fixture
def review(client,session,monkeypatch,tmp_path):
    settings=Settings(_env_file=None,saas_foundation_enabled=True,saas_application_review_enabled=True,
        pilot_auth_enabled=True,pilot_auth_username='operator',
        pilot_auth_password='unit-test-only-operator-password-of-safe-length-2026',arvectum_data_dir=str(tmp_path))
    monkeypatch.setattr(router,'get_settings',lambda:settings)
    tenant,a=_seed(client,'Synthetic application reviewer A')
    _,b=_seed(client,'Synthetic application reviewer B')
    _legal(client,a);_legal(client,b)
    member=session.scalar(select(SaasMember).where(SaasMember.tenant_id==tenant['tenant_id']))
    run='toa-run-fixture-approval';session.add(SaasRun(tenant_id=tenant['tenant_id'],run_id=run,created_by_member_id=member.id));session.commit()
    p=packet();calls=[]
    def observe(run_id):
        calls.append(run_id)
        return p
    monkeypatch.setattr(checklist_bundle_gate,'observe_application',observe)
    raw,m=template('docx')
    payload={'signatory':'DIRECTOR','goods_used':False,
             'templates':{'application_form':{'base64_bytes':base64.b64encode(raw).decode(),'mapping':m.model_dump(mode='json')}}}
    return '/api/saas/runs/'+run+'/application-review/previews',a,b,payload,p,calls,settings


def create(client,review):
    path,a,_,payload,*_=review
    r=client.post(path,headers=_auth(a),json=payload)
    assert r.status_code==201,r.text
    return r.json()


def confirm(client,path,token,p,**kwargs):
    return client.post(path+'/'+p['preview_id']+'/confirm',headers=_auth(token),
        json={'archive_sha256':p['archive_sha256'],'confirm_reviewed_private_archive':True,**kwargs})


def test_authenticated_review_roundtrip(client,session,review):
    path,a,b,_,_,calls,_=review
    p=create(client,review)
    assert not p['application_ready'] and p['open_item_codes']
    assert p['status']=='PRIVATE_PREVIEW' and 'input_json' not in p
    archive=path+'/'+p['preview_id']+'/archive'
    r=client.get(archive,headers=_auth(a));assert r.status_code==200
    assert hashlib.sha256(r.content).hexdigest()==p['archive_sha256']
    assert r.headers['cache-control']=='no-store'
    assert client.get(archive,headers=_auth(b)).status_code==404
    n=len(calls)
    assert confirm(client,path,b,p).status_code==404
    assert len(calls)==n
    assert confirm(client,path,a,p,confirm_reviewed_private_archive=False).status_code==409
    assert confirm(client,path,a,p,archive_sha256='0'*64).status_code==409
    r=confirm(client,path,a,p);assert r.status_code==200,r.text
    d=r.json();assert d['status']=='INTERNAL_REVIEW_RECORDED' and d['reviewed_by_member_id']==p['created_by_member_id']
    assert not d['application_ready'] and not d['external_action_allowed'] and not d['signed']
    assert confirm(client,path,a,p).json()['decision_id']==d['decision_id']
    assert len(list(session.scalars(select(ApplicationReviewDecision))))==1
    history=client.get(path,headers=_auth(a)).json()
    assert history['historical_only'] and history['items'][0]['decision_id']==d['decision_id']
    assert client.get(path,headers=_auth(b)).status_code==404


@pytest.mark.parametrize('change',['source','fact','expired'])
def test_stale_preview_denied(client,session,review,monkeypatch,change):
    path,a,_,_,packet,_,_=review;p=create(client,review)
    if change=='source':
        next(iter(next(iter(packet['source_groups'].values())).values()))[0]['chunk_id']='changed'
    elif change=='expired':
        now=application_review.now_utc()
        monkeypatch.setattr(application_review,'now_utc',lambda:now+timedelta(minutes=16))
    else:
        from src.modules.company_profile_store.models import CompanyProfileFactVersion
        from src.modules.saas_foundation.models import SaasTenant
        stored=session.get(ApplicationReviewPreview,p['preview_id'])
        tenant=session.scalar(select(SaasTenant).where(SaasTenant.tenant_id==stored.tenant_id))
        session.add(CompanyProfileFactVersion(customer_id=tenant.customer_id,fact_key='draft_identity:legal_name',fact_group='IDENTITY',
            version_no=1,value_json={},source_type='OWNER_CONFIRMED',source_ref='fixture',expires_at=application_review.now_utc()+timedelta(days=1)))
        session.commit()
    assert confirm(client,path,a,p).status_code==409
    assert not list(session.scalars(select(ApplicationReviewDecision)))


def test_feature_roles_and_bounds(client,session,review,monkeypatch):
    path,a,b,payload,_,calls,settings=review
    assert client.post(path,json=payload).status_code==401
    assert client.post(path,headers=_auth(b),json=payload).status_code==404
    assert not calls
    for role in ('viewer','analyst','admin'):
        invite=client.post('/api/saas/invitations',headers=_auth(a),json={'role':role}).json()
        member=client.post('/api/saas/invitations/redeem',json={'invitation_code':invite['invitation_code'],'display_name':role}).json()
        tok=member['access_token'];_legal(client,tok)
        r=client.post(path,headers=_auth(tok),json=payload)
        assert r.status_code==(201 if role=='admin' else 403),r.text
        if role=='admin':
            p=r.json()
            assert confirm(client,path,a,p).status_code==404
            assert client.get(path+'/'+p['preview_id']+'/archive',headers=_auth(a)).status_code==404
        assert client.post('/api/saas/members/'+member['member_id']+'/revoke',headers=_auth(a)).status_code==200
        assert client.get(path,headers=_auth(tok)).status_code==401
    assert client.post(path,headers=_auth(a),content=b' '*1048577).status_code==413
    assert client.post(path,headers=_auth(a),json={'customer_id':'foreign'}).status_code==422
    monkeypatch.setattr(application_review,'MAX_PREVIEWS_PER_TENANT',1)
    assert client.post(path,headers=_auth(a),json=payload).status_code==429
    monkeypatch.setattr(router,'get_settings',lambda:settings.model_copy(update={'saas_application_review_enabled':False}))
    assert client.get(path,headers=_auth(a)).status_code==404


def test_expiry_preserves_history_and_consumes_quota(client,session,review,monkeypatch):
    path,owner,foreign,payload,*_=review
    p=create(client,review)
    now=application_review.now_utc()
    monkeypatch.setattr(application_review,'now_utc',lambda:now+timedelta(minutes=16))
    archive=path+'/'+p['preview_id']+'/archive'
    assert client.get(archive,headers=_auth(owner)).status_code==200  # current historical access
    assert client.get(archive,headers=_auth(foreign)).status_code==404
    assert confirm(client,path,owner,p).status_code==409
    monkeypatch.setattr(application_review,'MAX_PREVIEWS_PER_TENANT',1)
    assert client.post(path,headers=_auth(owner),json=payload).status_code==429
    assert client.get(path,headers=_auth(owner)).json()['items'][0]['preview_id']==p['preview_id']
    assert session.get(ApplicationReviewPreview,p['preview_id']) is not None
    assert not list(session.scalars(select(ApplicationReviewDecision)))
