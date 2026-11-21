"""Isolated HTTP acceptance with generated test records and synthetic source receipts."""
import hashlib
import io
import zipfile

from sqlalchemy import select
from test_apr05_saas_foundation import _auth, enabled  # noqa: F401
from test_authenticated_application_review import confirm, create, review  # noqa: F401
from test_operator_cashflow_calendar import cost
from test_qualification_readiness import NOW
from test_reviewed_commercial_drafts import assertion, offer

from src.modules.customer_registry.models import CustomerProfile
from src.modules.saas_foundation import application_review, router
from src.modules.saas_foundation.models import (
    ApplicationReviewPreview,
    SaasRun,
    SaasTenant,
)


def test_offer_export_http(client, session, review, monkeypatch):  # noqa: F811
    path, owner, other, payload, source, _, settings = review
    run = session.scalar(select(SaasRun).where(SaasRun.run_id == 'toa-run-fixture-approval'))
    tenant = session.scalar(select(SaasTenant).where(SaasTenant.tenant_id == run.tenant_id))
    company = session.scalar(select(CustomerProfile).where(CustomerProfile.customer_id == tenant.customer_id))
    company.inn = '1234567890'
    session.commit()
    monkeypatch.setattr(application_review, 'now_utc', lambda: NOW)
    settings = settings.model_copy(update={'saas_customer_draft_export_enabled': True})
    monkeypatch.setattr(router, 'get_settings', lambda: settings)
    terms = offer().model_copy(update={'procurement_ref': '32616444788'})
    assertion(session, 'draft_offer:32616444788', terms, customer_id=company.customer_id)
    payload.update(cost=cost().model_dump(mode='json'), offer_terms=terms.model_dump(mode='json'))
    p = create(client, review)
    route = path + '/' + p['preview_id'] + '/customer-draft'
    body = {'archive_sha256': p['archive_sha256'], 'decision_id': 'missing',
            'selection': ['price_offer'], 'confirm_unsigned_subset': True}
    assert client.post(route, headers=_auth(owner), json=body).status_code == 409
    d = confirm(client, path, owner, p)
    assert d.status_code == 200, d.text
    body['decision_id'] = d.json()['decision_id']
    assert d.json()['customer_draft_options'] == ['price_offer']
    assert client.post(route, headers=_auth(other), json=body).status_code == 404
    assert client.post(route, headers=_auth(owner), json={**body, 'confirm_unsigned_subset': False}).status_code == 409
    result = client.post(route, headers=_auth(owner), json=body)
    assert result.status_code == 200, result.text
    assert result.headers['x-draft-sha256'] == hashlib.sha256(result.content).hexdigest()
    assert result.headers['cache-control'] == 'no-store'
    stored = session.get(ApplicationReviewPreview, p['preview_id'])
    with zipfile.ZipFile(io.BytesIO(result.content)) as export, zipfile.ZipFile(io.BytesIO(stored.archive_bytes)) as private:
        assert export.namelist() == ['UNSIGNED-price-offer.docx']
        assert export.read(export.namelist()[0]) == private.read('drafts/price-offer.docx')
    assert client.post(route, headers=_auth(owner), json={**body, 'selection': ['declarations']}).status_code == 409
    monkeypatch.setattr(router, 'get_settings', lambda: settings.model_copy(update={'saas_customer_draft_export_enabled': False}))
    assert client.post(route, headers=_auth(owner), json=body).status_code == 404
    monkeypatch.setattr(router, 'get_settings', lambda: settings)
    next(iter(next(iter(source['source_groups'].values())).values()))[0]['chunk_id'] = 'changed'
    assert client.post(route, headers=_auth(owner), json=body).status_code == 409
