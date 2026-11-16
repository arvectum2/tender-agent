import hashlib
import json
import zipfile

import pytest

from scripts.research.prepare_sibur_archive_index import prepare


def fixture(tmp_path):
    p=tmp_path/'original.docx'
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('word/document.xml','<document/>')
    sha=hashlib.sha256(p.read_bytes()).hexdigest()
    target=tmp_path/(sha+'.docx');p.rename(target)
    url='https://www.sibur.ru/upload/tmp/example/a/one.docx'
    ref={'external_id':'1/1','source_sha256':'a'*64,'source_row':'1','source_url':'https://www.sibur.ru/archive'}
    rc={'status':'captured','sha256':sha,'url':url,'file':target.name,'bytes':target.stat().st_size,'mime':'application/docx','references':[ref]}
    (tmp_path/(hashlib.sha256(url.encode()).hexdigest()+'.json')).write_text(json.dumps(rc))
    meta={'capture_receipts':[{k:rc[k] for k in ('url','bytes','mime','file')}|{'reference':ref}],'dp_index':None}
    db=[{'sha256':sha,'external_id':'1/1','raw_meta':meta}]
    queue={'rows':[{'sha256':sha,'file':target.name,'size_bytes':target.stat().st_size,'p0_scope':True,'tags':['electrical'],'project_ids':['AGHK'],'source_refs':[{'external_id':'1/1','source_url':url,'list_sha256':'a'*64,'source_row':'1'}]}]}
    return queue,db,sha,target


def test_exact_receipts_and_dedup(tmp_path):
    q,db,sha,p=fixture(tmp_path)
    assert prepare(q,tmp_path,db,set())['counts']['ready']==1
    assert prepare(q,tmp_path,db,{sha})['review'][0]['reason']=='already_indexed'
    assert prepare(q,tmp_path,[],set())['review'][0]['reason']=='committed_receipt_missing'
    db[0]['raw_meta']['capture_receipts'][0]['reference']['source_url']='wrong'
    assert prepare(q,tmp_path,db,set())['counts']['ready']==0


def test_changed_bytes_fail_closed(tmp_path):
    q,db,sha,p=fixture(tmp_path);p.write_bytes(b'bad')
    with pytest.raises(ValueError,match='hash mismatch'):
        prepare(q,tmp_path,db,set())


def test_unreconciled_index_and_duplicates_fail_closed(tmp_path):
    q,db,sha,p=fixture(tmp_path);db[0]['raw_meta']['dp_index']={'unexpected':True}
    with pytest.raises(ValueError,match='unreconciled'):
        prepare(q,tmp_path,db,set())
    db[0]['raw_meta']['dp_index']=None;q['rows']*=2
    with pytest.raises(ValueError,match='duplicate queue'):
        prepare(q,tmp_path,db,set())


def test_pdf_left_for_review(tmp_path):
    q,db,sha,p=fixture(tmp_path);q['rows'][0]['file']=sha+'.pdf'
    assert prepare(q,tmp_path,db,set())['review'][0]['reason']=='format_review'
