"""Dossier review gates on prior synthetic archive fixtures."""
import json

import pytest
from test_apr03b_ri223_archive_copilot import NUMBER
from test_apr03b_ri223_attachment_evidence import processor, setup_attachment
from test_apr03b_ri223_zip_evidence import bundle, fixture

from src.modules.tender_operator_agent_demo import ri223_review_dossier as dossier
from src.modules.tender_operator_agent_demo.ri223_offline_intake import import_archive


def setup_run(tmp_path,monkeypatch,*,archive=False,expand=False):
    if archive:
        root,notice,original=fixture(tmp_path,monkeypatch,bundle([('a.txt',b'first'),('b.txt',b'second')]))
    else:
        root,notice,original,_=setup_attachment(tmp_path,monkeypatch)
    run_id=import_archive(root,notice,NUMBER,attachments=[original],processor=processor,expand_zip=expand)
    run=root/run_id
    meta=json.loads((run/'metadata.json').read_text())
    monkeypatch.setattr(dossier,'checked_search_run',lambda _:(run,json.loads((run/'metadata.json').read_text())))
    return run_id,run,meta


@pytest.mark.parametrize('change',['none','parent','child','member_removed','duplicate','unexpected_role','receipt'])
def test_inventory_rederived(tmp_path,monkeypatch,change):
    _,run,meta=setup_run(tmp_path,monkeypatch,archive=True,expand=True)
    if change=='parent':(run/'input'/meta['files'][1]['stored_name']).write_bytes(b'bad')
    elif change=='child':(run/'input'/meta['files'][2]['stored_name']).write_bytes(b'bad')
    elif change=='member_removed':meta['files'].pop()
    elif change=='duplicate':meta['files'].append(dict(meta['files'][2]))
    elif change=='unexpected_role':meta['files'][2]['source']='user_upload'
    elif change=='receipt':meta['files'][2]['ri223_receipts']=[]
    out=dossier.verified_inventory(run,meta)
    assert out['archived_bytes_complete']==(change=='none')
    if change=='none':
        assert out['projection_complete'] and out['members_verified']==2


def test_opaque_is_not_complete(tmp_path,monkeypatch):
    _,run,meta=setup_run(tmp_path,monkeypatch,archive=True)
    out=dossier.verified_inventory(run,meta)
    assert out['archived_bytes_complete'] and not out['projection_complete'] and out['opaque_containers']==1


def test_no_search_without_originals(tmp_path,monkeypatch):
    run_id,run,meta=setup_run(tmp_path,monkeypatch)
    meta['files'].pop()
    monkeypatch.setattr(dossier,'search_run_documents',lambda *x:pytest.fail('incomplete set searched'))
    out=dossier.build_archived_review(run_id,run,meta)
    assert out['status']=='UNKNOWN' and not out['domains'] and not out['go_eligible']


@pytest.mark.parametrize('change',['none','during_search'])
def test_review_never_decides(tmp_path,monkeypatch,change):
    run_id,run,meta=setup_run(tmp_path,monkeypatch)
    calls=[]
    def search(*args):
        calls.append(args[1].query)
        if len(calls)==1 and change=='during_search':
            (run/'input'/meta['files'][1]['stored_name']).write_bytes(b'changed')
        return {'status':'UNKNOWN','citations':[]}
    monkeypatch.setattr(dossier,'search_run_documents',search)
    out=dossier.build_archived_review(run_id,run,meta)
    assert len(calls)==9 and not out['go_eligible'] and out['decision']=='NOT_DECIDED'
    if change=='none':
        assert out['status']=='RI223_ARCHIVED_REVIEW_ONLY' and out['source_backed_domains']==0
        assert len(out['domains'])==9 and not out['requirements_verified']
    else:assert out['status']=='UNKNOWN' and not out['domains']
