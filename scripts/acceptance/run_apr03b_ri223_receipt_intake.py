"""Offline acceptance of six original RI223 archives with configured trust anchor."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.acceptance.apr08_browser_harness import run_browser
from src.modules.tender_operator_agent_demo import router as operator_router
from src.modules.tender_operator_agent_demo.evidence_ri223_archive import (
    ri223_archive_observation,
    trusted_pins,
)
from src.modules.tender_operator_agent_demo.ri223_offline_intake import import_archive
from src.shared.api.middleware import TenderPilotBasicAuthMiddleware
from src.shared.config.settings import get_settings

ROOT=Path('/Users/master/arvectum-runtime/eis-223fz-corpus/2026-10-08')


def main():
    pins=trusted_pins()
    assert len(pins)==6
    sources={n:ROOT/n/('documentation-archive.zip' if n=='32616376947' else 'ri223-soap.zip') for n in pins}
    before={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
    assert before=={n:p[0] for n,p in pins.items()}
    with TemporaryDirectory(prefix='apr03b-ri223-intake-') as tmp:
        root=Path(tmp)
        runs={}
        os.environ['AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR']=tmp
        for n,archive in sources.items():
            run=import_archive(root,archive,n);runs[n]=run
            meta=json.loads((root/run/'metadata.json').read_text())
            r=ri223_archive_observation(root/run,meta)
            assert r['status']=='PINNED_RI223_ARCHIVED_NOTICE' and not r['bid_ready']
            assert meta['attachments_status']=='not_imported' and meta['status']=='needs_review'
            if n=='32616376947':
                assert r['lot_count']==2 and 'single_lot_initial_sum' not in r['fields']
            if n in ('32616445866','32616447910'):
                assert r['protocols_observed'] and not r['award_attested']
            print('RI223_RECEIPT_CASE',n,r['lot_count'],len(r['citations']),r['protocols_observed'])
        password=secrets.token_urlsafe(32)
        os.environ.update(AI_CORP_PILOT_AUTH_ENABLED='true',AI_CORP_PILOT_AUTH_USERNAME='apr08-replay',
                          AI_CORP_PILOT_AUTH_PASSWORD=password,AI_CORP_PILOT_AUTH_PROTECTED_PREFIXES='/pilot/tender-agent,/api/demo/tender-agent',
                          AI_CORP_PILOT_AUTH_PUBLIC_PATHS='/health')
        get_settings.cache_clear()
        app=FastAPI();app.include_router(operator_router.router)
        app.add_middleware(TenderPilotBasicAuthMiddleware,username='apr08-replay',password=password,
                           protected=('/pilot/tender-agent','/api/demo/tender-agent'),public=('/health',))
        with TestClient(app) as client:
            for run in runs.values():
                path=f'/api/demo/tender-agent/runs/{run}/analyze'
                assert client.post(path,auth=('apr08-replay',password)).status_code==409
        for number,scenario in [('32616444788','ri223'),('32616376947','ri223-multilot')]:
            target=Path(os.environ['APR08_SCREENSHOT_DIR'])/scenario;target.mkdir()
            run_browser(app,runs[number],password,target,scenario=scenario)
    assert before=={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
    print('APR03B_RI223_RECEIPT_INTAKE_PASS 6 original archives, 6 full-analysis denials, 2 Chromium scenarios, original ZIPs unchanged')


if __name__=='__main__':
    main()
