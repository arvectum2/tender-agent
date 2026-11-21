from __future__ import annotations

import hashlib
import json
import zipfile

import pytest
from test_apr03b_ri223_archive_copilot import NUMBER, setup_case
from test_apr03b_ri223_receipt_intake import catalog

from src.modules.tender_operator_agent_demo.ri223_attachment_evidence import (
    attachment_quote_allowed,
)
from src.modules.tender_operator_agent_demo.ri223_offline_intake import import_archive
from src.shared.document_processing import ProcessedChunk, ProcessedDocument


def setup_attachment(tmp_path, monkeypatch, ext='docx'):
    source=tmp_path/'source';source.mkdir()
    setup_case(source,monkeypatch)
    xml=source/'input'/'notice.xml'
    name='spec.'+ext
    raw=xml.read_bytes().replace(b'<lots>',f'<attachments><document><contentUid>fixture</contentUid><fileName>{name}</fileName><url>https://zakupki.gov.ru/test?uid=fixture</url></document></attachments><lots>'.encode())
    xml.write_bytes(raw)
    archive=source/'input'/'ri223.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('notice.xml',raw)
    original=tmp_path/'original.bin';original.write_bytes(b'synthetic exact original')
    h=lambda x: hashlib.sha256(x).hexdigest()
    doc={'name':name,'source_kind':'purchaseNotice','xml_sha256':h(raw),'sha256':h(original.read_bytes()),'bytes':original.stat().st_size}
    record={'registry_number':NUMBER,'archive_sha256':h(archive.read_bytes()),'selected_xml_sha256':h(raw),'observed_version':'1','documents':[doc],'archived_attachment_reference_coverage_complete':True}
    catalog(tmp_path,monkeypatch,[record])
    root=tmp_path/'runs';root.mkdir(mode=0o700)
    return root,archive,original,record


def processor(**kw):
    text='Условия оплаты услуг согласно договору.'
    chunk=ProcessedChunk(0,text,hashlib.sha256(text.encode()).hexdigest(),0,len(text),10,'fixture-chunk')
    return ProcessedDocument('extracted',text,(chunk,),'resource','document',kw['canonical_uri'])


def test_verified_import_and_tamper(tmp_path,monkeypatch):
    root,archive,original,_=setup_attachment(tmp_path,monkeypatch)
    run=root/import_archive(root,archive,NUMBER,attachments=[original],processor=processor)
    meta=json.loads((run/'metadata.json').read_text())
    f=meta['files'][1]
    assert meta['status']=='needs_review' and meta['ri223_attachment_extraction']['searchable']==1
    assert attachment_quote_allowed(run,meta,f)
    (run/'input'/f['stored_name']).write_bytes(b'changed')
    assert not attachment_quote_allowed(run,meta,f)


@pytest.mark.parametrize('change',['missing','wrong_bytes','receipt_reference','incomplete_receipt','symlink'])
def test_reject_before_processing(tmp_path,monkeypatch,change):
    root,archive,original,record=setup_attachment(tmp_path,monkeypatch)
    paths=[original]
    if change=='missing':paths=[]
    elif change=='wrong_bytes':original.write_bytes(b'changed')
    elif change=='receipt_reference':
        record['documents'][0]['xml_sha256']='a'*64
        catalog(tmp_path,monkeypatch,[record])
    elif change=='incomplete_receipt':
        record['archived_attachment_reference_coverage_complete']=False
        catalog(tmp_path,monkeypatch,[record])
    else:
        link=tmp_path/'link';link.symlink_to(original);paths=[link]
    def forbidden(**kw):pytest.fail('unverified original reached processor')
    with pytest.raises(ValueError):import_archive(root,archive,NUMBER,attachments=paths,processor=forbidden)
    assert not list(root.iterdir())


def test_rar_preserved_without_expansion(tmp_path,monkeypatch):
    root,archive,original,_=setup_attachment(tmp_path,monkeypatch,ext='rar')
    def forbidden(**kw):pytest.fail('compressed container reached processor')
    run=root/import_archive(root,archive,NUMBER,attachments=[original],processor=forbidden)
    meta=json.loads((run/'metadata.json').read_text())
    f=meta['files'][1]
    assert f['extraction_status']=='unsupported' and meta['ri223_attachment_extraction']['searchable']==0
    assert (run/'input'/f['stored_name']).read_bytes()==original.read_bytes()


@pytest.mark.parametrize('tamper',['none','parent','child','path','receipt','parent_id','alias'])
def test_rar_projection_and_lineage(tmp_path,monkeypatch,tamper):
    from src.modules.tender_operator_agent_demo import (
        ri223_container_evidence as container,
    )
    from src.modules.tender_operator_agent_demo.ri223_attachment_evidence import (
        verified_container_lineage,
    )
    from src.tender_research.providers.ri223_rar_members import Ri223RarMember

    root,archive,original,_=setup_attachment(tmp_path,monkeypatch,ext='rar')
    child=Ri223RarMember('docs/spec.docx','spec.docx',b'actual projected fixture')
    def extract(path):
        assert path.read_bytes()==original.read_bytes()
        return (child,)
    monkeypatch.setattr(container,'extract_ri223_rar_members',extract)
    run=root/import_archive(root,archive,NUMBER,attachments=[original],processor=processor,expand_rar=True)
    meta=json.loads((run/'metadata.json').read_text())
    p,f=meta['files'][1:]
    assert meta['ri223_attachment_extraction']['container_members']==1
    assert meta['ri223_attachment_extraction']['searchable']==1
    assert p['source']=='ri223_attachment' and f['source']=='ri223_container_member'
    if tamper=='parent':(run/'input'/p['stored_name']).write_bytes(b'changed')
    elif tamper=='child':(run/'input'/f['stored_name']).write_bytes(b'changed')
    elif tamper=='path':f['ri223_container']['member_path']='docs/other.docx'
    elif tamper=='receipt':f['ri223_receipts']=[]
    elif tamper=='parent_id':f['ri223_container']['parent_file_id']='FILE-99'
    elif tamper=='alias':meta['files'].append(dict(p))
    result=verified_container_lineage(run,meta,f)
    if tamper=='none':
        assert result['member_path']==child.path and result['parent_name']=='spec.rar'
        assert result['member_sha256']==hashlib.sha256(child.content).hexdigest()
    else:assert result is None


@pytest.mark.parametrize('path',['../escape.pdf','docs/*.pdf','docs/other.rar','/absolute.pdf','docs/a?.pdf','docs/a[1].pdf'])
def test_unsafe_projection_paths(tmp_path,monkeypatch,path):
    from pathlib import PurePosixPath

    from src.modules.tender_operator_agent_demo import (
        ri223_container_evidence as container,
    )
    from src.tender_research.providers.ri223_rar_members import Ri223RarMember

    root,archive,original,_=setup_attachment(tmp_path,monkeypatch,ext='rar')
    monkeypatch.setattr(container,'extract_ri223_rar_members',lambda _:(Ri223RarMember(path,PurePosixPath(path).name,b'bad'),))
    def forbidden(**kw):pytest.fail('unsafe child reached processor')
    with pytest.raises(ValueError):import_archive(root,archive,NUMBER,attachments=[original],processor=forbidden,expand_rar=True)
    assert not list(root.iterdir())
