"""Synthetic HTTP/SQLite exercise of named independent form review."""
import hashlib
import io
from datetime import timedelta

import pytest
from docx import Document
from sqlalchemy import select
from test_apr05_saas_foundation import _auth, _legal, enabled  # noqa: F401
from test_authenticated_application_review import review  # noqa: F401
from test_source_bound_form_fill import NOW, fact, template

from src.modules.application_package_generator import original_form_source
from src.modules.customer_registry.models import CustomerProfile
from src.modules.saas_foundation import original_form_review as service
from src.modules.saas_foundation import router
from src.modules.saas_foundation.models import (
    OriginalFormReviewReceipt,
    SaasMember,
    SaasRun,
    SaasTenant,
)


@pytest.fixture
def scenario(client, session, review, monkeypatch):  # noqa: F811
    path, creator, foreign, _, _, _, settings = review
    run = session.scalar(select(SaasRun).where(SaasRun.run_id == 'toa-run-fixture-approval'))
    tenant = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == run.tenant_id))
    company = session.scalar(select(CustomerProfile).where(CustomerProfile.customer_id == tenant.customer_id))
    company.inn = '1234567890'
    session.commit()
    fact(session, 'legal_name', company.legal_name, customer=company.customer_id)
    fact(session, 'inn', company.inn, customer=company.customer_id)
    owner = session.scalar(select(SaasMember).where(SaasMember.tenant_id == tenant.tenant_id))
    members = []
    for name in ('assigned synthetic admin', 'unassigned synthetic admin'):
        invite = client.post('/api/saas/invitations', headers=_auth(creator), json={'role':'admin'}).json()
        member = client.post('/api/saas/invitations/redeem', json={
            'invitation_code':invite['invitation_code'], 'display_name':name}).json()
        _legal(client, member['access_token'])
        members.append(member)
    raw, mapping = template('docx')
    snapshot = {'customer_id':company.customer_id, 'run_id':run.run_id, 'item_code':'application_form',
                'file_id':'fixture-form', 'template_sha256':mapping.template_sha256, 'observed_version':'1'}
    monkeypatch.setattr(original_form_source, 'observe_original_form', lambda *a:(raw, dict(snapshot)))
    monkeypatch.setattr(service, 'now_utc', lambda:NOW)
    settings = settings.model_copy(update={'saas_original_form_review_enabled':True})
    monkeypatch.setattr(router, 'get_settings', lambda:settings)
    payload = {'reviewer_id':members[0]['member_id'], 'item_code':'application_form',
               'file_id':'fixture-form', 'mapping':mapping.model_dump(mode='json')}
    return {'path':path.replace('application-review/previews','original-form-review/candidates'),
            'creator':creator, 'foreign':foreign, 'reviewer':members[0]['access_token'],
            'unassigned':members[1]['access_token'], 'owner_id':owner.id, 'payload':payload,
            'company_id':company.customer_id, 'snapshot':snapshot, 'settings':settings}


def create(client, s):
    r = client.post(s['path'], headers=_auth(s['creator']), json=s['payload'])
    assert r.status_code == 201, r.text
    return r.json()


def ack(client, s, p, token=None, **changes):
    body = {'candidate_sha256':p['candidate_sha256'], 'document_sha256':p['document_sha256'],
            'confirm_exact_private_form':True, **changes}
    return client.post(s['path']+'/'+p['candidate_id']+'/acknowledge',
                       headers=_auth(token or s['reviewer']), json=body)


def test_named_independent_acknowledgement(client, session, scenario, monkeypatch):
    s = scenario
    assert client.post(s['path'], headers=_auth(s['creator']),
        json={**s['payload'], 'reviewer_id':s['owner_id']}).status_code == 422
    p = create(client,s)
    route = s['path']+'/'+p['candidate_id']+'/document'
    for token in (s['foreign'],s['unassigned']):
        assert client.get(route,headers=_auth(token)).status_code == 404
        assert ack(client,s,p,token).status_code == 404
    assert ack(client,s,p,s['creator']).status_code == 403
    assert ack(client,s,p,confirm_exact_private_form=False).status_code == 409
    assert ack(client,s,p,document_sha256='0'*64).status_code == 409
    downloaded = client.get(route,headers=_auth(s['reviewer']))
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == p['document_sha256']
    assert '1234567890' in Document(io.BytesIO(downloaded.content)).paragraphs[1].text
    d = ack(client,s,p)
    assert d.status_code == 200,d.text
    result = d.json()
    assert result['status'] == 'INDEPENDENT_INTERNAL_REVIEW_RECORDED'
    assert not result['application_ready'] and not result['external_export_allowed']
    assert ack(client,s,p).json()['receipt_id'] == result['receipt_id']
    assert len(list(session.scalars(select(OriginalFormReviewReceipt)))) == 1
    assert client.get(s['path'],headers=_auth(s['unassigned'])).json()['items'] == []
    monkeypatch.setattr(router,'get_settings',lambda:s['settings'].model_copy(update={'saas_original_form_review_enabled':False}))
    assert client.get(route,headers=_auth(s['reviewer'])).status_code == 404


@pytest.mark.parametrize('change',['source','fact','expiry','revoked'])
def test_review_rechecks_current_state(client, session, scenario, monkeypatch, change):
    s = scenario
    p = create(client,s)
    if change == 'source':
        s['snapshot']['observed_version'] = '2'
    elif change == 'fact':
        fact(session,'inn','1234567890',customer=s['company_id'],version=2)
    elif change == 'expiry':
        monkeypatch.setattr(service,'now_utc',lambda:NOW+timedelta(minutes=31))
    else:
        r = client.post('/api/saas/members/'+s['payload']['reviewer_id']+'/revoke',headers=_auth(s['creator']))
        assert r.status_code == 200
    assert ack(client,s,p).status_code == (401 if change == 'revoked' else 409)
    assert not list(session.scalars(select(OriginalFormReviewReceipt)))
