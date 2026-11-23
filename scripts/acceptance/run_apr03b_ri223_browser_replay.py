"""Replay one independently pinned RI223 procurement without importing live data."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import tempfile
import zipfile
from pathlib import Path

from scripts.acceptance.apr06_mixed_archive_selection import observe, verified_downloads
from scripts.acceptance.apr08_browser_harness import run_browser
from scripts.acceptance.run_apr08_real_dp_replay import inventory
from src.modules.tender_operator_agent_demo.evidence_ri223_archive import PINS, SOURCE

NUMBER='32616444788'
ROOT=Path('/Users/master/arvectum-runtime/eis-223fz-corpus/2026-10-08')
RUN='toa-run-20261117120000-223abc'


def main():
    manifest=ROOT/'manifest.json'
    assert hashlib.sha256(manifest.read_bytes()).hexdigest()=='e27d6a93c0f641e27743ccaaaf3be790dbcac9c04f138e9cb8dc5a0ce9716de2'
    record=next(x for x in json.loads(manifest.read_bytes())['records'] if x['number']==NUMBER)
    source=ROOT/NUMBER/'ri223-soap.zip'
    before=inventory(ROOT/NUMBER)
    raw,row=observe(source,NUMBER,PINS[NUMBER][0])
    docs=verified_downloads(ROOT,record,raw)
    assert len(docs)==4 and row['selected_xml_sha256']==PINS[NUMBER][1]
    member=raw.raw_payload['evidence']['xml_member']
    with tempfile.TemporaryDirectory(prefix='apr03b-ri223-') as tmp:
        root=Path(tmp);directory=root/RUN/'input';directory.mkdir(parents=True)
        archive=directory/'ri223.zip';shutil.copyfile(source,archive)
        with zipfile.ZipFile(archive) as z:
            xml=z.read(member)
        (directory/member).write_bytes(xml)
        meta={'run_id':RUN,'procurement_id':NUMBER,'procurement_source':SOURCE,
              'archive_stored_name':archive.name,'files':[{'file_id':'FILE-01','original_name':member,
              'display_name':member,'stored_name':member,'extension':'.xml','size_bytes':len(xml),'content_type':'application/xml'}],
              'created_at':'2026-11-17T12:00:00+00:00','mode':'procurement_search_intake','tender_title':raw.title,
              'tender_category':'Архивная проверка','customer_name':'Не установлен в оболочке теста','law':'223-ФЗ',
              'notice_number':NUMBER,'status':'ready_to_analyze','archive_downloaded':True,'attachments_status':'downloaded'}
        (root/RUN/'metadata.json').write_text(json.dumps(meta))
        os.environ['AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR']=str(root)
        from fastapi import FastAPI

        from src.modules.tender_operator_agent_demo import router as operator_router
        from src.modules.tender_operator_agent_demo.evidence_grounded_questions import (
            GroundedQuestion,
            answer_grounded_question,
        )
        from src.shared.api.middleware import TenderPilotBasicAuthMiddleware
        from src.shared.config.settings import get_settings

        password=secrets.token_urlsafe(32)
        os.environ.update(AI_CORP_PILOT_AUTH_ENABLED='true',AI_CORP_PILOT_AUTH_USERNAME='apr08-replay',
                          AI_CORP_PILOT_AUTH_PASSWORD=password,AI_CORP_PILOT_AUTH_PROTECTED_PREFIXES='/pilot/tender-agent,/api/demo/tender-agent',
                          AI_CORP_PILOT_AUTH_PUBLIC_PATHS='/health')
        get_settings.cache_clear()
        app=FastAPI();app.include_router(operator_router.router)
        app.add_middleware(TenderPilotBasicAuthMiddleware,username='apr08-replay',password=password,
                           protected=('/pilot/tender-agent','/api/demo/tender-agent'),public=('/health',))
        proof=answer_grounded_question(RUN,GroundedQuestion(question='Покажи архивные сведения 223-ФЗ'))
        assert proof['status']=='PINNED_RI223_ARCHIVED_NOTICE' and len(proof['citations'])==5
        original=inventory(root/RUN)
        run_browser(app,RUN,password,Path(os.environ['APR08_SCREENSHOT_DIR']),scenario='ri223')
        assert inventory(root/RUN)==original
        (directory/member).write_bytes(xml+b' ')
        tamper=answer_grounded_question(RUN,GroundedQuestion(question='Покажи архивные сведения 223-ФЗ'))
        assert tamper['status']=='UNKNOWN' and not tamper['citations']
    assert inventory(ROOT/NUMBER)==before
    print('APR03B_RI223_REPLAY_PASS original archive and 4 attachments verified; browser and tamper gate; originals unchanged')


if __name__=='__main__':
    main()
