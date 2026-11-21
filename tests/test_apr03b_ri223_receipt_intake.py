from __future__ import annotations

import hashlib
import json

import pytest
from fastapi import HTTPException

from src.modules.tender_operator_agent_demo import evidence_ri223_archive as ri
from src.modules.tender_operator_agent_demo.ri223_offline_intake import import_archive
from src.modules.tender_operator_agent_demo.ri223_receipt_catalog import (
    configured_catalog,
)
from src.modules.tender_operator_agent_demo.upload_service_legacy import (
    analyze_uploaded_demo_run,
    append_files_to_demo_run,
)


def catalog(tmp_path, monkeypatch, rows):
    path=tmp_path/'catalog.json';raw=json.dumps({'historical_ri223_cases':rows}).encode();path.write_bytes(raw)
    monkeypatch.setenv('AI_CORP_RI223_RECEIPT_CATALOG',str(path))
    monkeypatch.setenv('AI_CORP_RI223_RECEIPT_CATALOG_SHA256',hashlib.sha256(raw).hexdigest())
    return path


def row(n='32600000000'):
    return {'registry_number':n,'archive_sha256':'a'*64,'selected_xml_sha256':'b'*64,'observed_version':'1'}


def test_catalog_configured_and_tamper_no_fallback(tmp_path,monkeypatch):
    p=catalog(tmp_path,monkeypatch,[row(),row('32600000001')])
    assert len(configured_catalog())==2
    p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises(ValueError):ri.trusted_pins()
    result=ri.ri223_archive_observation(tmp_path,{'procurement_source':ri.SOURCE,'procurement_id':'32616444788'})
    assert result['status']=='UNKNOWN' and result['reason']=='RI223_CATALOG_UNVERIFIED'


@pytest.mark.parametrize('rows',[[row(),row()],[{**row(),'observed_version':'0'}],[{**row(),'archive_sha256':'x'*64}],[],[None]])
def test_invalid_catalog(tmp_path,monkeypatch,rows):
    catalog(tmp_path,monkeypatch,rows)
    with pytest.raises((TypeError,ValueError)):configured_catalog()


def test_offline_import_and_mutation_gate(tmp_path,monkeypatch):
    from test_apr03b_ri223_archive_copilot import NUMBER, setup_case

    source=tmp_path/'source';source.mkdir()
    setup_case(source,monkeypatch)
    a,x,v=ri.PINS[NUMBER]
    catalog(tmp_path,monkeypatch,[{'registry_number':NUMBER,'archive_sha256':a,'selected_xml_sha256':x,'observed_version':v}])
    root=tmp_path/'runs';root.mkdir(mode=0o700)
    archive=source/'input'/'ri223.zip'
    run=import_archive(root,archive,NUMBER)
    meta=json.loads((root/run/'metadata.json').read_text())
    assert meta['status']=='needs_review' and meta['attachments_status']=='not_imported'
    assert ri.ri223_archive_observation(root/run,meta)['status']=='PINNED_RI223_ARCHIVED_NOTICE'
    monkeypatch.setenv('AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR',str(root))
    for fn in (lambda:analyze_uploaded_demo_run(run),lambda:append_files_to_demo_run(run_id=run,uploads=[])):
        with pytest.raises(HTTPException) as e:fn()
        assert e.value.status_code==409
    assert json.loads((root/run/'metadata.json').read_text())==meta
    archive.write_bytes(archive.read_bytes()+b' ')
    with pytest.raises(ValueError):import_archive(root,archive,NUMBER)
    assert list(root.iterdir())==[root/run]
