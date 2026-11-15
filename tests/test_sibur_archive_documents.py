from scripts.research.run_sibur_archive_documents import ALLOWED, captures


def test_supported_archive_formats():
    assert {".docx",".xlsx",".pdf",".pptx"} <= ALLOWED
    assert ".exe" not in ALLOWED and ".rar" not in ALLOWED


def test_review_receipt_excluded(tmp_path):
    import json

    (tmp_path/("a"*64+".json")).write_text(json.dumps({"status":"review"}))
    assert captures(tmp_path,{})==[]


def test_requested_priority_must_match_committed_source_pair():
    from scripts.research.run_sibur_archive_documents import acquisition_order
    a='https://www.sibur.ru/a.xlsx';b='https://www.sibur.ru/b.pdf';c='https://www.sibur.ru/c.docx';bad='https://unverified.example/a.xlsx'
    refs={a:[{'external_id':'A'}],b:[{'external_id':'B'}],c:[{'external_id':'C'}]}
    request=[{'url':b,'ids':['B'],'p0':True},{'url':c,'ids':['WRONG'],'p0':True},{'url':bad,'ids':['A'],'p0':True}]
    assert acquisition_order(refs,{'A'},request)==[b,a,c]
