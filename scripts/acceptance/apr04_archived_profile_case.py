"""Private historical packet, disposable DB; no production tenant or original upload."""
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.modules.company_profile_store.qualification_archived_readiness import (
    review_archived_profile,
)
from src.modules.company_profile_store.qualification_readiness import review_profile
from src.modules.company_profile_store.schemas import AppendCompanyProfileFactRequest
from src.modules.company_profile_store.service import append_company_profile_fact
from src.modules.customer_registry.schemas import CreateCustomerRequest
from src.modules.customer_registry.service import create_customer
from src.modules.tender_operator_agent_demo.ri223_attachment_evidence import read_bytes
from src.shared.db import models as _models  # noqa: F401
from src.shared.db.base import Base

REVIEW_CODES={'current_registry':'registry','sme_membership':'sme','current_tax':'tax',
              'completed_experience':'experience','license_scope_review':'license','certificate_scope_review':'certificate',
              'sro_scope_review':'sro'}


def replay_profile(run_id):
    p=Path(os.environ['APR04_PRIVATE_REGISTRATION_PACKET'])
    raw=read_bytes(p,32768)
    assert hashlib.sha256(raw).hexdigest()==os.environ['APR04_PRIVATE_REGISTRATION_PACKET_SHA256']
    d=json.loads(raw)
    assert d['production_import_allowed'] is False and d['current_registry_verified'] is False
    assert d['current_sme_membership'] is None and d['live_customer_id'] is None
    identity=d['identity'];refs=d['source_documents']
    assert len(refs)==2 and not any(r['original_stored_on_mac_mini'] for r in refs)
    with TemporaryDirectory(prefix='apr04-profile-readiness-') as tmp:
        root=Path(tmp)
        engine=create_engine('sqlite:///'+str(root/'review.sqlite'))
        try:
            Base.metadata.create_all(engine)
            with Session(engine) as s:
                cust,existed=create_customer(s,CreateCustomerRequest(legal_name=identity['legal_name'],
                            inn=identity['inn'],kpp=identity['kpp'],customer_status='PROSPECT'))
                assert not existed
                cid=cust.customer_id
                for i,(key,value) in enumerate((('registration_snapshot',d['registration_observations']),('tax_registration_snapshot',d['tax_registration_observations']))):
                    append_company_profile_fact(s,customer_id=cid,fact_key=key,payload=AppendCompanyProfileFactRequest(
                        fact_group='IDENTITY',value={'historical_only':True,'as_of_date':d['as_of_date'],'observations':value},
                        source_type='HISTORICAL_DOCUMENT_REVIEW',source_ref='historical-packet-sha256:'+hashlib.sha256(raw).hexdigest()+':'+str(i)))
            with Session(engine) as s:
                now=datetime(2026,11,18,10,tzinfo=UTC)
                general=review_profile(s,customer_id=cid,root=root,requirements=REVIEW_CODES,now=now)
                assert len(general['requirements'])==7 and all(r['state']=='MISSING' for r in general['requirements'])
                assert general['screening_preferences_state']=='MISSING' and not general['go_eligible']
                out=review_archived_profile(s,customer_id=cid,root=root,run_id=run_id,now=now)
                req=out['requirement']
                assert req['status']=='ARCHIVED_SME_REQUIREMENT_ATTESTED',req['status']
                assert out['profile_readiness']['requirements'][0]['state']=='MISSING'
                assert out['recommendation']=='DEFER' and not out['go_eligible']
                print('APR04_REAL_PROFILE_READINESS_PASS',req['procurement_number'],req['procedure_context'],
                      'historical facts only, seven evidence gaps, SME UNKNOWN, DEFER',flush=True)
        finally:
            engine.dispose()
