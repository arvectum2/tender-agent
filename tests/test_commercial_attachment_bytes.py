import io
import zipfile
from hashlib import sha256

import pytest

from src.modules.saas_foundation.commercial_attachment_bytes import (
    CT,
    TYPES,
    W,
    inspect_attachment,
)


def docx_fixture(text='Поставка и монтаж оборудования', extras=None, main_override=None):
    main, _, mime=TYPES['docx']; doc=f'<w:document xmlns:w="{W[1:-1]}"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>'
    parts={'[Content_Types].xml':f'<Types xmlns="{CT[1:-1]}"><Override PartName="/{main}" ContentType="{mime}"/></Types>',main:doc if main_override is None else main_override,**(extras or {})}
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,raw in parts.items():z.writestr(name,raw)
    return stream.getvalue()


def test_docx_preview_limited_literal_with_provenance():
    raw=docx_fixture();r=inspect_attachment(raw,'docx')
    assert r['sha256']==sha256(raw).hexdigest()
    assert r['text_preview']==[{'part':'word/document.xml','paragraph_index':1,'text':'Поставка и монтаж оборудования'}]
    assert not r['text_preview_complete'] and not r['requirements_verified'] and not r['malware_free_verified']
    assert len(inspect_attachment(docx_fixture('x'*13000),'docx')['text_preview'][0]['text'])==12000


@pytest.mark.parametrize('extras',[{'../escape.xml':'x'},{'word/vbaProject.bin':'x'},{'word/embeddings/b.bin':'x'},{'word/DOCUMENT.XML':'x'},{'word/_rels/document.xml.rels':'<Relationships><Relationship TargetMode="External" Target="https://evil.invalid/"/></Relationships>'},{'big.bin':b'x'*(2*1024*1024+1)}])
def test_unsafe_ooxml_rejected(extras):
    with pytest.raises(ValueError):inspect_attachment(docx_fixture(extras=extras),'docx')


def test_format_mismatch_xml_declarations_and_pdf_bounds():
    for raw,kind in [(docx_fixture(),'xlsx'),(b'<html>error</html>','pdf'),(docx_fixture(),'zip'),(b'', 'docx'),(b'x'*(2*1024*1024+1),'pdf'),(docx_fixture(main_override=b'<!DOCTYPE a [<!ENTITY x SYSTEM "file:///etc/passwd">]><a/>'),'docx')]:
        with pytest.raises(ValueError):inspect_attachment(raw,kind)
    pdf=inspect_attachment(b'%PDF-1.7\nfixture\n%%EOF\n','pdf')
    assert pdf['format_check']=='PDF_HEADER_AND_EOF_ONLY' and not pdf['text_preview']
