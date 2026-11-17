"""Replay the actual pinned RAR and validate nested citation lineage."""
import hashlib
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from scripts.acceptance.apr08_browser_harness import run_browser
from scripts.acceptance.run_apr08_real_dp_replay import inventory
from src.modules.tender_operator_agent_demo.ri223_offline_intake import import_archive

ROOT=Path('/Users/master/arvectum-runtime/eis-223fz-corpus/2026-10-08/32616445795')


def replay_container(runs,app,password):
    before=inventory(ROOT)
    archive=ROOT/'ri223-soap.zip'
    rar=ROOT/'attachments/01-3727.rar'
    receipt=Path('docs/acceptance/ri223_32616445795_original_scoring_receipt_2026-10-13.json')
    assert hashlib.sha256(receipt.read_bytes()).hexdigest()=='b5f2591cf4ef5a452330e00ba3e66c09997fae0ea2bed41a1d6633283a306d0c'
    proof=json.loads(receipt.read_bytes())
    assert hashlib.sha256(rar.read_bytes()).hexdigest()==proof['original_attachment_sha256']
    run=import_archive(runs,archive,'32616445795',attachments=[rar],expand_rar=True)
    directory=runs/run
    meta=json.loads((directory/'metadata.json').read_text())
    count=meta['ri223_attachment_extraction']
    members=[f for f in meta['files'] if f['source']=='ri223_container_member']
    assert count['container_members']==len(members)==19
    assert meta['status']=='needs_review' and not count['full_analysis_allowed']
    by_path={f['ri223_container']['member_path']:f for f in members}
    for path,sha in [('evaluation_pdf_member','evaluation_pdf_sha256'),('parallel_legacy_doc_member','parallel_legacy_doc_sha256')]:
        assert by_path[proof[path]]['ri223_container']['member_sha256']==proof[sha]
    assert all(f['ri223_container']['parent_sha256']==proof['original_attachment_sha256'] for f in members)
    print('RI223_RAR_ACTUAL',count,[(f['extension'],f['extraction_status']) for f in members],flush=True)
    url=f'/api/demo/tender-agent/workspace/runs/{run}/evidence-search'
    auth=('apr08-replay',password)
    saved=inventory(directory)
    with TestClient(app) as c:
        assert c.post(url,json={'query':'критерий оценки'}).status_code==401
        result=c.post(url,auth=auth,json={'query':'критерий оценки'})
        assert result.status_code==200
        packet=result.json();assert packet['status']=='VERIFIED_EXCERPTS_ONLY',packet['status']
        assert packet['citations'] and all(x['ri223_container']['parent_sha256']==proof['original_attachment_sha256'] and x['ri223_container']['member_sha256']==x['original_sha256'] for x in packet['citations'])
        assert c.post(f'/api/demo/tender-agent/runs/{run}/analyze',auth=auth).status_code==409
        if os.environ.get('APR08_BROWSER_ACCEPTANCE')=='1':
            run_browser(app,run,password,Path(os.environ['APR08_SCREENSHOT_DIR']),scenario='ri223-container')
        assert inventory(directory)==saved
        parent=directory/'input'/meta['files'][1]['stored_name']
        blob=parent.read_bytes();parent.write_bytes(blob+b' ')
        result=c.post(url,auth=auth,json={'query':'критерий оценки'}).json()
        assert result['status']=='UNKNOWN' and not result['citations']
        parent.write_bytes(blob)
        for f in members:
            if f.get('evidence_chunks'):
                p=directory/'input'/f['stored_name'];p.write_bytes(p.read_bytes()+b' ')
        result=c.post(url,auth=auth,json={'query':'критерий оценки'}).json()
        assert result['status']=='UNKNOWN' and not result['citations']
    assert inventory(ROOT)==before
    print('APR03B_RI223_RAR_REPLAY_PASS',len(members),count['searchable'],'parent/child tamper UNKNOWN; scoring hashes match; originals unchanged')
