import io
import shutil

import pytest
from openpyxl import Workbook
from test_commercial_attachment_bytes import docx_fixture

from src.modules.saas_foundation.commercial_text_evidence import project_text


def workbook_fixture():
    wb=Workbook();ws=wb.active;ws.title='Требования'
    ws['A1']='Поставщик должен иметь опыт поставки';ws['B2']='Срок поставки 30 дней';ws['C3']='=1+2';ws['D4']=42
    hidden=wb.create_sheet('Hidden');hidden.sheet_state='hidden';hidden['A1']='Обязательный скрытый текст'
    stream=io.BytesIO();wb.save(stream);return stream.getvalue()


def pdf_fixture():
    content=b'BT /F1 12 Tf 30 100 Td (Delivery terms) Tj ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>', b'<< /Length '+str(len(content)).encode()+b' >>\nstream\n'+content+b'\nendstream',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    raw=b'%PDF-1.4\n';offsets=[]
    for i,obj in enumerate(objects,1):
        offsets.append(len(raw));raw+=str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    xref=len(raw);raw+=b'xref\n0 6\n0000000000 65535 f \n'+b''.join(f'{n:010d} 00000 n \n'.encode() for n in offsets)
    return raw+b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(xref).encode()+b'\n%%EOF\n'


def test_xlsx_literal_cells_and_candidate_provenance():
    r=project_text(workbook_fixture(),'xlsx')
    assert r['status']=='PARTIAL_PREVIEW'
    assert [(x['location']['cell'],x['text']) for x in r['fragments']]==[('A1','Поставщик должен иметь опыт поставки'),('B2','Срок поставки 30 дней'),('D4','42')]
    assert r['fragments'][0]['location']['sheet']=='Требования'
    assert r['requirement_candidates'][0]['categories']==['qualification','technical']
    assert r['requirement_candidates'][1]['categories']==['delivery']
    assert all(not r[k] for k in ('coverage_complete','requirements_verified','platform_original_verified','qualification_verified','external_submission_allowed'))


def test_docx_projection_preserves_location_and_limits():
    r=project_text(docx_fixture('Требования: '+'x'*3000),'docx')
    f=r['fragments'][0];assert f['location']=={'part':'word/document.xml','paragraph_index':1}
    assert f['fragment_truncated'] and len(f['text'])==1000
    assert r['requirement_candidates'][0]['fragment_id']==f['fragment_id']


def test_pdf_disabled_and_missing_extractor(monkeypatch):
    raw=pdf_fixture();assert project_text(raw,'pdf')['status']=='EXTRACTION_DISABLED_OR_UNSUPPORTED'
    monkeypatch.setattr(shutil,'which',lambda _:None)
    assert project_text(raw,'pdf',pdf_enabled=True)['status']=='EXTRACTOR_UNAVAILABLE'


@pytest.mark.skipif(shutil.which('pdftotext') is None, reason='Poppler unavailable')
def test_real_pdf_bounded_page_projection():
    r=project_text(pdf_fixture(),'pdf',pdf_enabled=True)
    assert r['status']=='PARTIAL_PREVIEW',r
    assert r['fragments'][0]['location']['page']==1
    assert 'Delivery terms' in r['fragments'][0]['text']
