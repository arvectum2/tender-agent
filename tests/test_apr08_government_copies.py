import hashlib
import io
import zipfile

import pytest

from src.modules.tender_operator_agent_demo import evidence_government_copies as copies


@pytest.fixture
def snapshots(tmp_path, monkeypatch):
    catalog={}
    for day, amendment in [('2026-09-11','279'),('2026-11-03','278')]:
        lines=['5 апреля 2013 года','N 44-ФЗ','Список изменяющих документов',f'от 04.08.2026 N {amendment}-ФЗ','Статья 45. Заголовок оглавления','Статья 45. Тестовый заголовок','Тестовый абзац.','Статья 46. Следующая статья']
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as z:
            z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+''.join('<w:p><w:r><w:t>'+x+'</w:t></w:r></w:p>' for x in lines)+'</w:body></w:document>')
        name=day+'.docx'; data=raw.getvalue();(tmp_path/name).write_bytes(data)
        catalog[('44-ФЗ',day)]=(name,hashlib.sha256(data).hexdigest(),'https://example.invalid/'+name,{'45':6})
    monkeypatch.setattr(copies,'SOURCES',catalog)
    monkeypatch.setenv('AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR',str(tmp_path))
    return tmp_path


def test_explicit_copy_skips_toc_and_never_claims_current_law(snapshots):
    r=copies.government_copy_observation('44-ФЗ','2026-11-03','45')
    assert r['status']=='HISTORICAL_STATUTE_SNAPSHOT_EXCERPT'
    assert r['citations'][0]['excerpt']=='Статья 45. Тестовый заголовок\nТестовый абзац.'
    assert r['snapshot_bytes_verified'] and not r['statute_text_verified'] and not r['current_law_verified']
    assert r['reviewed_effective_interval'] is None
    assert copies.government_copy_observation('44-ФЗ','2026-11-17','45')['status']=='UNKNOWN'


def test_list_comparison_and_tamper(snapshots):
    r=copies.compare_government_copies('44-ФЗ')
    assert r['status']=='GOVERNMENT_COPY_LIST_COMPARISON' and not r['amendment_coverage_complete']
    assert r['observations'][0]=={'amendment':'278-ФЗ','listed_in_older_excerpt':False,'listed_in_newer_excerpt':True}
    p=snapshots/'2026-09-11.docx';p.write_bytes(p.read_bytes()+b' ')
    assert copies.compare_government_copies('44-ФЗ')['status']=='UNKNOWN'


def test_exact_questions_and_as_of_refused(snapshots,monkeypatch):
    from src.modules.tender_operator_agent_demo import evidence_grounded_questions as qa
    monkeypatch.setattr(qa,'checked_search_run',lambda _:(None,{}))
    for q,status in [('Покажи статью 45 44-ФЗ из копии от 03.11.2026','HISTORICAL_STATUTE_SNAPSHOT_EXCERPT'),('Сравни списки изменений 44-ФЗ','GOVERNMENT_COPY_LIST_COMPARISON'),('Покажи статью 45 44-ФЗ на дату 03.11.2026','UNKNOWN')]:
        r=qa.answer_grounded_question('run',qa.GroundedQuestion(question=q));assert r['status']==status and not r['legal_requirement_attested'] and not r['bid_ready']


def test_pdf_projection_requires_both_hashes(tmp_path,monkeypatch):
    import json

    raw=b'%PDF synthetic fixture';sha=hashlib.sha256(raw).hexdigest()
    (tmp_path/'synthetic.pdf').write_bytes(raw)
    data={'raw_sha256':sha,'page_count':65,'pages':{'1':['18 июля 2011 года N 223-ФЗ','Список изменяющих документов'],'9':['Статья 3. Тестовый заголовок','Тестовый блок']}}
    projection=json.dumps(data,ensure_ascii=False).encode();p=tmp_path/'223fz-mchs-blocks.json';p.write_bytes(projection)
    monkeypatch.setattr(copies,'SOURCES',{('223-ФЗ','2025-06-07'):('synthetic.pdf',sha,'https://example.invalid/synthetic.pdf',{'3':(9,1)})})
    monkeypatch.setattr(copies,'PDF_PROJECTION_SHA',hashlib.sha256(projection).hexdigest())
    monkeypatch.setenv('AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR',str(tmp_path))
    result=copies.government_copy_observation('223-ФЗ','2025-06-07','3')
    assert result['status']=='HISTORICAL_STATUTE_SNAPSHOT_EXCERPT' and result['citations'][0]['projection_sha256']==copies.PDF_PROJECTION_SHA
    p.write_bytes(projection+b' ')
    assert copies.government_copy_observation('223-ФЗ','2025-06-07','3')['status']=='UNKNOWN'
    p.write_bytes(projection);(tmp_path/'synthetic.pdf').write_bytes(raw+b' ')
    assert copies.government_copy_observation('223-ФЗ','2025-06-07','3')['status']=='UNKNOWN'
