"""Synthetic HTTP acceptance of internal proposal-only console."""
from sqlalchemy import func, select
from test_apr05_saas_foundation import _auth, _operator, enabled  # noqa: F401
from test_authenticated_application_review import create, review  # noqa: F401

from src.modules.saas_foundation import router
from src.modules.saas_foundation.models import (
    ApplicationReviewPreview,
    PrivateReviewOrderLink,
    PrivateReviewRetentionProposal,
    SaasAuditEvent,
)

PAGE='/api/operator/saas/retention-console'


def test_retention_operator_proposals_and_scope(client, session, review, monkeypatch):  # noqa: F811
    path, owner, foreign, _, _, _, settings=review
    p=create(client,review)
    tenant=session.get(ApplicationReviewPreview,p['preview_id']).tenant_id
    root='/api/operator/saas/tenants/'+tenant+'/retention'
    basic=_operator(client)
    headers={**basic,'X-Retention-Intent':'proposal-only'}
    assert client.get(PAGE,headers=basic).status_code==404
    monkeypatch.setattr(router,'get_settings',lambda:settings.model_copy(update={'saas_retention_operator_enabled':True}))
    assert client.get(PAGE).status_code==401
    assert client.get(root,headers=_auth(owner)).status_code==401
    assert client.get(root,headers=_auth(foreign)).status_code==401
    page=client.get(PAGE,headers=basic)
    assert page.status_code==200
    assert page.headers['cache-control']=='no-store'
    assert "frame-ancestors 'none'" in page.headers['content-security-policy']
    assert 'Первичная привязка' in page.text
    result=client.get(root,headers=basic).json()
    assert result['accounting']['archives']['count']==1
    assert result['documents'][0]['id']==p['preview_id']
    assert 'archive_bytes' not in str(result) and 'input_json' not in str(result)
    body={'expected_revision':0,'confirm_proposal_only':True,
          'schedule':{'order_ref':'fixture-order','policy_ref':'fixture-policy','working_days':30,'backup_days':90}}
    assert client.post(root+'/proposals',headers=basic,json=body).status_code==403
    assert client.post(root+'/proposals',headers={**headers,'Origin':'https://foreign.invalid'},json=body).status_code==403
    assert client.post(root+'/proposals',headers=headers,json={**body,'confirm_proposal_only':False}).status_code==409
    assert client.post(root+'/proposals',headers={**headers,'Content-Type':'application/json'},content=b' '*8193).status_code==413
    response=client.post(root+'/proposals',headers=headers,json=body)
    assert response.status_code==201,response.text
    proposal=response.json()
    assert proposal['revision']==1 and proposal['planning']['deletion_authorized'] is False
    assert client.post(root+'/proposals',headers=headers,json=body).status_code==409
    link={'proposal_id':proposal['proposal_id'],'document_kind':'archive','document_id':p['preview_id'],
          'evidence_ref':'fixture-link','confirm_proposal_only':True}
    assert client.post(root+'/links',headers=headers,json={**link,'document_id':'missing'}).status_code==404
    assert client.post(root+'/links',headers=headers,json=link).status_code==201
    assert client.post(root+'/links',headers=headers,json=link).status_code==409
    assert client.post(root+'/proposals',headers=headers,json={**body,'expected_revision':1}).status_code==201
    d=client.get(root,headers=basic).json()
    assert d['accounting']['archives']['proposal_superseded']==1
    assert d['proposals'][0]['revision']==2
    assert d['operator_identity_verified'] is False and d['deletion_authorized'] is False
    assert session.scalar(select(func.count(PrivateReviewOrderLink.id)))==1
    assert session.scalar(select(func.count(PrivateReviewRetentionProposal.id)))==2
    assert session.scalar(select(func.count(SaasAuditEvent.id)).where(
        SaasAuditEvent.event_type.in_(['retention_proposal_recorded','retention_link_proposed'])))==3
    assert client.get(path+'/'+p['preview_id']+'/archive',headers=_auth(owner)).status_code==200


def test_retention_correction_history_and_scope(client, session, review, monkeypatch):  # noqa: F811
    from src.modules.saas_foundation.models import (
        PrivateReviewLinkCorrection,
        SaasTenant,
    )
    path, owner, foreign, _, _, _, settings=review
    p=create(client,review)
    tenant=session.get(ApplicationReviewPreview,p['preview_id']).tenant_id
    other=session.scalar(select(SaasTenant.tenant_id).where(SaasTenant.tenant_id!=tenant))
    root='/api/operator/saas/tenants/'+tenant+'/retention'
    other_root='/api/operator/saas/tenants/'+other+'/retention'
    headers={**_operator(client),'X-Retention-Intent':'proposal-only'}
    monkeypatch.setattr(router,'get_settings',lambda:settings.model_copy(update={'saas_retention_operator_enabled':True}))
    body={'expected_revision':0,'confirm_proposal_only':True,
          'schedule':{'order_ref':'fixture-order','policy_ref':'fixture-policy','working_days':30,'backup_days':90}}
    initial=client.post(root+'/proposals',headers=headers,json=body).json()['proposal_id']
    external=client.post(other_root+'/proposals',headers=headers,json=body).json()['proposal_id']
    link=client.post(root+'/links',headers=headers,json={'proposal_id':initial,'document_kind':'archive',
        'document_id':p['preview_id'],'evidence_ref':'fixture-link','confirm_proposal_only':True}).json()['link_id']
    target=client.post(root+'/proposals',headers=headers,json={**body,'expected_revision':1}).json()['proposal_id']
    request={'link_id':link,'expected_revision':0,'proposal_id':target,
             'evidence_ref':'fixture-correction','confirm_proposal_only':True}
    endpoint=root+'/link-corrections'
    for payload,status in (({**request,'proposal_id':external},404),
                           ({**request,'proposal_id':initial},409),
                           ({**request,'link_id':'missing'},404),
                           ({**request,'confirm_proposal_only':False},409)):
        assert client.post(endpoint,headers=headers,json=payload).status_code==status
    assert client.post(endpoint,headers=_auth(owner),json=request).status_code==401
    assert client.post(endpoint,headers={**headers,'Origin':'https://foreign.invalid'},json=request).status_code==403
    assert client.post(other_root+'/link-corrections',headers=headers,json=request).status_code==404
    assert client.get(other_root+'/links/'+link+'/history',headers=headers).status_code==404
    assert client.get(root+'/links/'+link+'/history',headers=_auth(foreign)).status_code==401
    response=client.post(endpoint,headers=headers,json=request)
    assert response.status_code==201,response.text
    assert response.json()['revision']==1 and response.json()['deletion_authorized'] is False
    assert client.post(endpoint,headers=headers,json=request).status_code==409
    assert client.post(endpoint,headers=headers,json={**request,'expected_revision':1}).status_code==409
    history=client.get(root+'/links/'+link+'/history',headers=headers).json()['history']
    assert [(r['revision'],r['proposal_id']) for r in history]==[(0,initial),(1,target)]
    details=client.get(root,headers=headers).json()
    assert details['documents'][0]['original_proposal']==initial
    assert details['documents'][0]['proposed_link']==target
    assert details['documents'][0]['link_revision']==1
    assert details['accounting']['archives']['corrected_links']==1
    assert details['accounting']['archives']['proposal_superseded']==0
    assert session.get(PrivateReviewOrderLink,link).proposal_id==initial
    assert session.scalar(select(func.count(PrivateReviewLinkCorrection.id)))==1
    assert session.scalar(select(func.count(SaasAuditEvent.id)).where(
        SaasAuditEvent.event_type=='retention_link_corrected'))==1
    assert client.get(path+'/'+p['preview_id']+'/archive',headers=_auth(owner)).status_code==200
