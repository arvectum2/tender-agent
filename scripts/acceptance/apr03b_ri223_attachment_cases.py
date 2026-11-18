"""Actual archived cases inside the isolated DP replay harness."""
import hashlib
import json
import os
import secrets
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.acceptance.apr08_browser_harness import run_browser
from scripts.acceptance.run_apr08_real_dp_replay import inventory
from src.modules.tender_operator_agent_demo import router as operator_router
from src.modules.tender_operator_agent_demo.ri223_offline_intake import import_archive
from src.modules.tender_operator_agent_demo.ri223_receipt_catalog import (
    configured_receipts,
)
from src.shared.api.middleware import TenderPilotBasicAuthMiddleware
from src.shared.config.settings import get_settings

ROOT=Path('/Users/master/arvectum-runtime/eis-223fz-corpus/2026-10-08')


def replay(runs):
    manifest=ROOT/'manifest.json'
    assert hashlib.sha256(manifest.read_bytes()).hexdigest()=='e27d6a93c0f641e27743ccaaaf3be790dbcac9c04f138e9cb8dc5a0ce9716de2'
    recs={r['number']:r for r in json.loads(manifest.read_bytes())['records']}
    catalog=configured_receipts();assert catalog and len(catalog)==6
    before={n:inventory(ROOT/n) for n in catalog}
    password=secrets.token_urlsafe(32)
    os.environ.update(AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR=str(runs),
        AI_CORP_PILOT_AUTH_ENABLED='true',AI_CORP_PILOT_AUTH_USERNAME='apr08-replay',AI_CORP_PILOT_AUTH_PASSWORD=password,
        AI_CORP_PILOT_AUTH_PROTECTED_PREFIXES='/pilot/tender-agent,/api/demo/tender-agent',AI_CORP_PILOT_AUTH_PUBLIC_PATHS='/health')
    get_settings.cache_clear()
    app=FastAPI();app.include_router(operator_router.router)
    app.add_middleware(TenderPilotBasicAuthMiddleware,username='apr08-replay',password=password,
        protected=('/pilot/tender-agent','/api/demo/tender-agent'),public=('/health',))
    all_runs={};unique=references=searchable=0
    incomplete_refused=False
    for number,r in sorted(catalog.items()):
        archive=ROOT/number/('documentation-archive.zip' if number=='32616376947' else 'ri223-soap.zip')
        if not r['archived_attachment_reference_coverage_complete']:
            try:import_archive(runs,archive,number,attachments=[])
            except ValueError:
                print('INCOMPLETE_RECEIPT_REFUSED',number)
                incomplete_refused=number=='32616376947'
            else:raise AssertionError('incomplete receipt accepted')
            continue
        paths=([ROOT/number/'attachments/01-3727.rar'] if number=='32616445795' else
               list({a['sha256']:ROOT/number/f"attachment-{a['id']:02d}.bin" for a in recs[number]['attachments']}.values()))
        run=import_archive(runs,archive,number,attachments=paths)
        all_runs[number]=run
        meta=json.loads((runs/run/'metadata.json').read_text())
        counts=meta['ri223_attachment_extraction'];unique+=counts['unique_originals'];references+=counts['references'];searchable+=counts['searchable']
        assert meta['status']=='needs_review' and not counts['full_analysis_allowed']
        print('RI223_ATTACHMENTS',number,counts,[(f['extension'],f.get('extraction_status')) for f in meta['files'][1:]],flush=True)
    assert (unique,references)==(9,11) and searchable>=3
    if os.environ.get('APR067_DOMAIN_COVERAGE')=='1':
        from scripts.quality.apr067_ri223_domain_coverage import measure_runs

        measure_runs(runs,all_runs,ROOT,incomplete_refused)
    if os.environ.get('APR067_GAP_REVIEW')=='1':
        from scripts.quality.apr067_ri223_gap_review import observe, summarize

        rows=[row for number,run_id in sorted(all_runs.items()) if number!='32616445795' for row in observe(run_id)]
        print('APR067_RI223_GAP_REVIEW_PASS',json.dumps(summarize(rows),ensure_ascii=False),flush=True)
    if os.environ.get('APR067_PROJECTION_REUSE')=='1':
        from scripts.quality.apr067_ri223_projection_reuse import measure

        measure(runs,ROOT)
    if os.environ.get('APR067_INFLECTION_SEARCH')=='1':
        from scripts.quality.apr067_ri223_inflection_search import (
            measure as measure_inflection,
        )

        measure_inflection(runs,all_runs,ROOT,incomplete_refused)
    if os.environ.get('APR067_CLAUSE_RANKING')=='1':
        from scripts.quality.apr067_ri223_clause_ranking import (
            measure as measure_clause_ranking,
        )

        measure_clause_ranking(runs,all_runs,ROOT,incomplete_refused)
    run=all_runs['32616444788'];directory=runs/run
    url=f'/api/demo/tender-agent/workspace/runs/{run}/evidence-search'
    with TestClient(app) as c:
        assert c.post(url,json={'query':'договор'}).status_code==401
        auth=('apr08-replay',password)
        result=c.post(url,auth=auth,json={'query':'договор'})
        assert result.status_code==200
        packet=result.json();assert packet['status']=='VERIFIED_EXCERPTS_ONLY' and packet['citations'],packet['status']
        assert all(x['original_sha256'] in {d['sha256'] for d in catalog['32616444788']['documents']} for x in packet['citations'])
        assert c.post(f'/api/demo/tender-agent/runs/{run}/analyze',auth=auth).status_code==409
        saved=inventory(directory)
        if os.environ.get('APR08_BROWSER_ACCEPTANCE')=='1':
            run_browser(app,run,password,Path(os.environ['APR08_SCREENSHOT_DIR']),scenario='ri223-attachments')
        assert inventory(directory)==saved
        for f in json.loads((directory/'metadata.json').read_text())['files'][1:]:
            if f.get('evidence_chunks'):
                p=directory/'input'/f['stored_name'];p.write_bytes(p.read_bytes()+b' ')
        t=c.post(url,auth=auth,json={'query':'договор'}).json()
        assert t['status']=='UNKNOWN' and not t['citations']
    if os.environ.get('APR03B_RAR_ACCEPTANCE')=='1':
        from scripts.acceptance.apr03b_ri223_container_case import replay_container

        replay_container(runs,app,password)
    if os.environ.get('APR03B_ZIP_ACCEPTANCE')=='1':
        from scripts.acceptance.apr03b_ri223_zip_fixture import replay_zip

        replay_zip(runs,app,password)
    assert all(inventory(ROOT/n)==v for n,v in before.items())
    print('APR03B_RI223_ATTACHMENTS_REPLAY_PASS',unique,references,searchable,'source originals unchanged, tamper UNKNOWN')
