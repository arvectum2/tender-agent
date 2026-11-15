from scripts.research.run_sibur_archive_documents import ALLOWED, captures


def test_supported_archive_formats():
    assert {".docx",".xlsx",".pdf",".pptx"} <= ALLOWED
    assert ".exe" not in ALLOWED and ".rar" not in ALLOWED


def test_review_receipt_excluded(tmp_path):
    import json

    (tmp_path/("a"*64+".json")).write_text(json.dumps({"status":"review"}))
    assert captures(tmp_path,{})==[]
