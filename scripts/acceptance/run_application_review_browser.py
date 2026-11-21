"""Synthetic source receipt and real operator API/Chromium; never opens private archives."""
from __future__ import annotations

import json
import os
import secrets
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI

from scripts.acceptance.apr08_browser_harness import run_browser
from src.modules.tender_operator_agent_demo import router, workspace_application_review
from src.modules.tender_operator_agent_demo.ri223_application_source import (
    SOURCE_PARAGRAPHS,
)
from src.shared.api.middleware import TenderPilotBasicAuthMiddleware
from src.shared.config.settings import Settings

RUN='toa-run-20261118120000-123abc'


def main():
    with tempfile.TemporaryDirectory(prefix='application-review-synthetic-') as tmp:
        root=Path(tmp)
        directory=root/RUN/'input'
        directory.mkdir(parents=True)
        source=directory/'fixture.txt'
        source.write_text('Synthetic document for UI only')
        meta={'run_id':RUN,'procurement_id':'32616444788','procurement_source':'eis_223fz',
              'files':[{'file_id':'FILE-01','original_name':source.name,'display_name':source.name,
              'stored_name':source.name,'extension':'.txt','size_bytes':source.stat().st_size,
              'content_type':'text/plain'}],
              'created_at':'2026-11-18T12:00:00+00:00','mode':'procurement_search_intake',
              'tender_title':'Синтетическая проверка интерфейса','tender_category':'Тест',
              'customer_name':'Synthetic','law':'223-ФЗ','notice_number':'32616444788',
              'status':'ready_to_analyze','attachments_status':'downloaded'}
        (root/RUN/'metadata.json').write_text(json.dumps(meta))
        password=secrets.token_urlsafe(32)
        settings=Settings(pilot_auth_enabled=True,pilot_auth_username='apr08-replay',pilot_auth_password=password)
        packet={'procurement_number':'32616444788','status':'ARCHIVED_QUOTATION_CHECKLIST_REVIEW_ONLY',
            'source_groups':{sha:{k:[{'quote':q,'original_sha256':sha,'file_id':f'FILE-{i+1:02}',
            'chunk_id':'synthetic-'+k}] for k,q in items.items()} for i,(sha,items) in enumerate(SOURCE_PARAGRAPHS.items())}}
        app=FastAPI()
        app.include_router(router.router)
        app.add_middleware(TenderPilotBasicAuthMiddleware,username='apr08-replay',password=password,
            protected=('/pilot/tender-agent','/api/demo/tender-agent'),public=('/health',))
        with (patch.dict(os.environ,{'AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR':str(root)}),
              patch.object(router,'get_settings',return_value=settings),
              patch.object(workspace_application_review,'observe_application',return_value=packet)):
            run_browser(app,RUN,password,root,scenario='application-review-synthetic')


if __name__=='__main__':
    main()
