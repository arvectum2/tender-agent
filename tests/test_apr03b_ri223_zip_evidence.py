"""Synthetic ZIP adversarial fixtures; never actual EIS source claims."""
import hashlib
import io
import json
import stat
import warnings
import zipfile

import pytest
from test_apr03b_ri223_archive_copilot import NUMBER
from test_apr03b_ri223_attachment_evidence import processor, setup_attachment
from test_apr03b_ri223_receipt_intake import catalog

from src.modules.tender_operator_agent_demo.ri223_attachment_evidence import (
    verified_container_lineage,
)
from src.modules.tender_operator_agent_demo.ri223_container_evidence import project_zip
from src.modules.tender_operator_agent_demo.ri223_offline_intake import import_archive


def bundle(entries, compression=zipfile.ZIP_STORED):
    stream=io.BytesIO()
    with warnings.catch_warnings(),zipfile.ZipFile(stream,'w',compression=compression) as z:
        warnings.simplefilter('ignore',UserWarning)
        for name,data in entries:z.writestr(name,data)
    return stream.getvalue()


def fixture(tmp_path,monkeypatch,raw):
    root,archive,original,record=setup_attachment(tmp_path,monkeypatch,ext='zip')
    original.write_bytes(raw)
    record['documents'][0].update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    catalog(tmp_path,monkeypatch,[record])
    return root,archive,original


@pytest.mark.parametrize('tamper',['none','parent','child','member_path','container_format','receipt'])
def test_zip_lineage(tmp_path,monkeypatch,tamper):
    raw=bundle([('docs/',b''),('docs/spec.txt',b'exact fixture'),('docs/table.csv',b'a,b\n1,2')])
    root,archive,original=fixture(tmp_path,monkeypatch,raw)
    run=root/import_archive(root,archive,NUMBER,attachments=[original],processor=processor,expand_zip=True)
    meta=json.loads((run/'metadata.json').read_text())
    p,f,_=meta['files'][1:]
    assert meta['status']=='needs_review' and meta['ri223_attachment_extraction']['container_members']==2
    assert meta['ri223_attachment_extraction']['searchable']==2
    assert f['ri223_container']['container_format']=='ZIP'
    if tamper=='parent':(run/'input'/p['stored_name']).write_bytes(raw+b' ')
    elif tamper=='child':(run/'input'/f['stored_name']).write_bytes(b'wrong')
    elif tamper=='member_path':f['ri223_container']['member_path']='docs/table.csv'
    elif tamper=='container_format':f['ri223_container']['container_format']='RAR'
    elif tamper=='receipt':f['ri223_receipts']=[]
    bound=verified_container_lineage(run,meta,f)
    if tamper=='none':assert bound['member_path']=='docs/spec.txt' and bound['parent_sha256']==hashlib.sha256(raw).hexdigest()
    else:assert bound is None


@pytest.mark.parametrize('name',['../a.txt','/a.txt','C:/a.txt','a\\b.txt','dir//a.txt','dir/./a.txt','a.zip','a.rar','a.exe','a?.txt'])
def test_forbidden_paths(name):
    with pytest.raises(ValueError):project_zip(bundle([(name,b'bad')]))


def special_file(mode):
    info=zipfile.ZipInfo('file.txt');info.create_system=3;info.external_attr=mode<<16
    return info


@pytest.mark.parametrize('mode',[stat.S_IFLNK,stat.S_IFIFO,stat.S_IFCHR])
def test_special_file(mode):
    with pytest.raises(ValueError):project_zip(bundle([(special_file(mode),b'bad')]))


@pytest.mark.parametrize('entries',[
    [('a.txt',b'1'),('a.txt',b'2')],
    [('a.txt',b'1'),('a.txt/b.txt',b'2')],
    [('a.txt/',b''),('a.txt',b'2')],
    [('empty.txt',b'')],
    [(f'{i}.txt',b'1') for i in range(23)],
])
def test_reject_inventory(entries):
    with pytest.raises(ValueError):project_zip(bundle(entries))


def test_encrypted_flag_and_crc():
    raw=bytearray(bundle([('test.txt',b'original')]))
    i=raw.index(b'PK\x01\x02');raw[i+8]|=1;raw[6]|=1
    with pytest.raises(ValueError):project_zip(bytes(raw))
    raw=bytearray(bundle([('test.txt',b'original')]))
    raw[raw.index(b'original')]=ord('x')
    with pytest.raises(ValueError):project_zip(bytes(raw))


def test_ratio_and_preflight(tmp_path,monkeypatch):
    with pytest.raises(ValueError):project_zip(bundle([('bomb.txt',b'a'*1_000_000)],zipfile.ZIP_DEFLATED))
    root,archive,original=fixture(tmp_path,monkeypatch,bundle([('safe.txt',b'valid'),('../escape.txt',b'bad')]))
    def forbidden(**kw):pytest.fail('processor called before complete ZIP validation')
    with pytest.raises(ValueError):import_archive(root,archive,NUMBER,attachments=[original],processor=forbidden,expand_zip=True)
    assert not list(root.iterdir())


def test_opt_in(tmp_path,monkeypatch):
    root,archive,original=fixture(tmp_path,monkeypatch,bundle([('sample.txt',b'valid')]))
    run=root/import_archive(root,archive,NUMBER,attachments=[original],processor=processor)
    meta=json.loads((run/'metadata.json').read_text())
    assert meta['ri223_attachment_extraction']['container_members']==0
    assert meta['ri223_attachment_extraction']['searchable']==0
