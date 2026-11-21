"""Read-only profile claim lifecycle and tenant isolation."""
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.modules.company_profile_store.models import (
    CompanyDocument,
    CompanyDocumentVersion,
    CompanyProfileFactVersion,
)
from src.modules.company_profile_store.qualification_readiness import review_profile
from src.modules.customer_registry.models import CustomerProfile
from src.modules.document_store.models import ArtifactVersion, DocumentArtifact
from src.shared.db import models as _models  # noqa: F401
from src.shared.db.base import Base

NOW=datetime(2026,11,18,10,tzinfo=UTC)
REQUIREMENTS={'sme_membership':'sme','fsb_license':'license'}


@pytest.fixture
def fixture(tmp_path):
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        for cid,inn in [('owner','1234567890'),('other','0987654321')]:
            s.add(CustomerProfile(customer_id=cid,legal_name=cid,inn=inn,customer_status='PROSPECT'))
        s.commit()
        folder=tmp_path/'company-onboarding'/'owner'
        folder.mkdir(parents=True)
        p=folder/'document.pdf'
        p.write_bytes(b'%PDF-1.4\nsynthetic evidence, not a registry extract\n')
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        a=DocumentArtifact(artifact_ref='artifact',artifact_type='OTHER',file_name=p.name,storage_uri=str(p),checksum_sha256=sha,current_version=1)
        s.add(a);s.flush()
        s.add(ArtifactVersion(artifact_ref=a.artifact_ref,version_no=1,storage_uri=str(p),checksum_sha256=sha))
        doc=CompanyDocument(customer_id='owner',document_key='sme',document_type='STATUTORY',display_name='Fixture',artifact_ref=a.artifact_ref)
        s.add(doc);s.flush()
        s.add(CompanyDocumentVersion(company_document_id=doc.id,version_no=1,artifact_version_no=1,source_type='CUSTOMER_UPLOADED',
                                     source_ref='fixture',expires_at=NOW+timedelta(days=30)))
        s.commit()
        claim={'schema_version':'qualification-documentary-claim-v1','inn':'1234567890','requirement_code':'sme_membership',
               'observed_on':'2026-11-18','valid_through':'2026-12-01','owner_confirmed':True,
               'assertion':'PRESENT','document_key':'sme','document_version':1,'sha256':sha}
        yield s,tmp_path,p,claim,doc
    engine.dispose()


def add(s,value,*,version=1,expires=NOW+timedelta(days=30),source_type='OWNER_CONFIRMED',key='qualification_claim:sme_membership',group='OTHER'):
    s.add(CompanyProfileFactVersion(customer_id='owner',fact_key=key,fact_group=group,
        version_no=version,value_json=value,source_type=source_type,source_ref='synthetic reviewed claim',expires_at=expires))
    s.commit()


def result(s,root,cid='owner'):
    return review_profile(s,customer_id=cid,root=root,requirements=REQUIREMENTS,now=NOW)


def test_no_fact_no_qualification(fixture):
    s,root,_,_,_=fixture
    r=result(s,root)
    assert [x['state'] for x in r['requirements']]==['MISSING','MISSING']
    assert not r['go_eligible'] and r['legal_eligibility']=='NOT_ASSESSED'
    assert r['screening_preferences_state']=='MISSING'


@pytest.mark.parametrize('assertion',['PRESENT','ABSENT'])
def test_exact_owner_claim_only_candidate(fixture,assertion):
    s,root,_,claim,_=fixture
    add(s,{**claim,'assertion':assertion})
    r=result(s,root)
    assert r['documented_claim_count']==1
    row=r['requirements'][0]
    assert row['state']=='DOCUMENTED_OWNER_CLAIM_REVIEW_REQUIRED' and row['claim_assertion']==assertion
    assert row['legal_satisfied'] is None and not row['semantic_verified']
    assert result(s,root,'other')['documented_claim_count']==0


@pytest.mark.parametrize('change,expected',[
    ('wrong_inn','IDENTITY_SCOPE_OR_DATE_UNCONFIRMED'),('wrong_code','IDENTITY_SCOPE_OR_DATE_UNCONFIRMED'),
    ('stale','IDENTITY_SCOPE_OR_DATE_UNCONFIRMED'),('future','IDENTITY_SCOPE_OR_DATE_UNCONFIRMED'),
    ('expired','EXPIRED_OR_NO_EXPIRY'),('no_expiry','EXPIRED_OR_NO_EXPIRY'),
    ('unreviewed','UNREVIEWED_FACT'),('no_doc','DOCUMENT_MISSING_OR_WRONG_TYPE'),
    ('wrong_sha','ARTIFACT_BINDING_MISMATCH'),('tamper','DOCUMENT_BYTES_MISMATCH'),
    ('symlink','DOCUMENT_OUTSIDE_PRIVATE_STORE'),('new_version','DOCUMENT_VERSION_CHANGED'),
    ('unconfirmed','IDENTITY_SCOPE_OR_DATE_UNCONFIRMED')])
def test_bad_latest_never_falls_back(fixture,change,expected):
    s,root,p,claim,doc=fixture
    add(s,claim)
    d=dict(claim);opts={}
    if change=='wrong_inn':d['inn']='0987654321'
    elif change=='wrong_code':d['requirement_code']='other'
    elif change=='stale':d['observed_on']='2026-10-01'
    elif change=='future':d['observed_on']='2026-11-19'
    elif change=='expired':opts['expires']=NOW
    elif change=='no_expiry':opts['expires']=None
    elif change=='unreviewed':opts['source_type']='CUSTOMER_PROVIDED'
    elif change=='no_doc':d['document_key']='missing'
    elif change=='wrong_sha':d['sha256']='f'*64
    elif change=='tamper':p.write_bytes(b'%PDF-1.4\nchanged')
    elif change=='symlink':
        p.unlink();other=root/'outside.pdf';other.write_bytes(b'%PDF-1.4\n');p.symlink_to(other)
    elif change=='new_version':
        s.add(CompanyDocumentVersion(company_document_id=doc.id,version_no=2,artifact_version_no=2,source_type='CUSTOMER_UPLOADED',source_ref='new'))
        s.commit()
    elif change=='unconfirmed':d['owner_confirmed']=False
    add(s,d,version=2,**opts)
    row=result(s,root)['requirements'][0]
    assert row['state']==expected and row['fact_version']==2 and row['legal_satisfied'] is None


def test_preferences_not_qualification(fixture):
    s,root,_,_,_=fixture
    add(s,{'criteria':{'categories':['IT']},'qualification':{'licenses':['FSB']}},
        source_type='CUSTOMER_PROVIDED',key='supplier_profile')
    r=result(s,root)
    assert r['screening_preferences_state']=='OWNER_INPUT_REVIEW_REQUIRED'
    assert r['documented_claim_count']==0


def test_wrong_type_and_cross_tenant_document(fixture):
    s,root,p,claim,doc=fixture
    add(s,{**claim,'requirement_code':'fsb_license'},key='qualification_claim:fsb_license',group='LICENSE')
    assert result(s,root)['requirements'][1]['state']=='DOCUMENT_MISSING_OR_WRONG_TYPE'
    # A claim cannot attach another tenant's artifact by path.
    add(s,claim)
    a=s.query(ArtifactVersion).filter_by(artifact_ref=doc.artifact_ref).one()
    foreign=root/'company-onboarding'/'other'/'doc.pdf'
    foreign.parent.mkdir();foreign.write_bytes(p.read_bytes())
    a.storage_uri=str(foreign);s.commit()
    assert result(s,root)['requirements'][0]['state']=='DOCUMENT_OUTSIDE_PRIVATE_STORE'


def test_historical_identity_does_not_become_current_registry(fixture):
    s,root,_,_,_=fixture
    add(s,{'historical_only':True,'as_of_date':'2026-06-24'},key='registration_snapshot',group='IDENTITY',source_type='HISTORICAL_DOCUMENT_REVIEW')
    d=review_profile(s,customer_id='owner',root=root,requirements={'current_registry':'registry'},now=NOW)
    assert d['requirements'][0]['state']=='MISSING' and not d['go_eligible']
