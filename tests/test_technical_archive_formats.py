import hashlib
import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from scripts.research import technical_document_evidence as m


def office():
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:z.writestr('word/document.xml','<document><p><t>АСУ ТП</t></p></document>')
    return b.getvalue()


@pytest.mark.parametrize('ext,signature', [('.rar',b'Rar!\x1a\x07\x01\x00'),('.7z',b'7z\xbc\xaf\x27\x1c')])
def test_stream_exact_member(tmp_path,ext,signature):
    data=office();p=tmp_path/('input'+ext);p.write_bytes(signature+b'x'*1000)
    name='ТЗ.docx';verbose=f'-rw-r--r-- 0 0 0 {len(data)} Nov 27 12:00 {name}\n'
    with patch.object(m,'archive_stream',side_effect=[(name+'\n').encode(),verbose.encode(),data]) as stream:
        r=m.extract(p,hashlib.sha256(p.read_bytes()).hexdigest())
    assert r['status']=='extracted' and r['parts'][0]['member']==name
    assert r['parts'][0]['member_sha256']==hashlib.sha256(data).hexdigest()
    assert stream.call_args.args[0][-2:]==['--',name]


@pytest.mark.parametrize('name', ['../a.docx','/a.docx','C:/a.docx','a*.docx','a[1].docx'])
def test_bad_member_name(name):
    assert not m.safe_archive_name(name)


def test_unsafe_special_member_is_rejected(tmp_path):
    p=tmp_path/'input.rar';raw=b'Rar!\x1a\x07\x00'+b'x'*100;p.write_bytes(raw)
    with patch.object(m,'archive_stream',side_effect=[b'link.docx\n',b'lrwxrwxrwx 0 0 0 10 Nov 27 12:00 link.docx -> foo\n']):
        with pytest.raises(ValueError,match='special member'):list(m.external_archive_members(p,raw,'.rar'))


def test_bad_member_size_is_partial(tmp_path):
    p=tmp_path/'input.7z';raw=b'7z\xbc\xaf\x27\x1c'+b'x'*100;p.write_bytes(raw)
    with patch.object(m,'archive_stream',side_effect=[b'a.docx\n',b'-rw-r--r-- 0 0 0 5 Nov 27 12:00 a.docx\n',b'abc']):
        assert list(m.external_archive_members(p,raw,'.7z'))==[('a.docx',None,'archive member size mismatch')]

@pytest.mark.parametrize('ext,real_ext', [('.doc','.docx'),('.xls','.xlsx')])
def test_mislabeled_ooxml_uses_internal_format(ext,real_ext):
    raw=b'PK\x03\x04fixture'
    with patch.object(m,'office_parts',return_value=iter([('part','text')])) as parser:
        assert list(m.document_parts(raw,ext))==[('part','text')]
    parser.assert_called_once_with(raw,real_ext)

@pytest.mark.parametrize('ext', ['.doc','.xls','.pdf'])
def test_invalid_legacy_signature_rejected(ext):
    with pytest.raises(ValueError):list(m.document_parts(b'<html>not original</html>',ext))


def test_unavailable_backend_is_review(tmp_path):
    from scripts.research.run_technical_evidence import review_extract
    p=tmp_path/'doc.doc';p.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1')+b'fake')
    with patch.object(m,'archive_stream',side_effect=FileNotFoundError('backend')):
        r=review_extract(p,hashlib.sha256(p.read_bytes()).hexdigest())
    assert r['status']=='review' and not r['parts']
