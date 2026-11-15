import hashlib
import io
import zipfile

import pytest

from scripts.research.technical_document_evidence import extract, matches


def test_original_and_member_bound_pq_offsets(tmp_path):
    data=io.BytesIO()
    with zipfile.ZipFile(data,"w") as z:
        z.writestr("word/document.xml",'<document><p><t>Предусмотреть установку компенсации реактивной мощности УКРМ.</t></p></document>')
    p=tmp_path/"package.zip"
    with zipfile.ZipFile(p,"w") as z:
        z.writestr("ТЗ.docx",data.getvalue())
        z.writestr("../legacy.doc",b"legacy")
    sha=hashlib.sha256(p.read_bytes()).hexdigest()
    r=extract(p,sha)
    assert r["status"]=="partial_review" and len(r["parts"])==1
    t=r["parts"][0]
    assert t["member"]=="ТЗ.docx" and t["member_sha256"]==hashlib.sha256(data.getvalue()).hexdigest()
    assert "pq_equipment" in t["matches"]
    hit=t["matches"]["pq_equipment"][0]
    assert hit["excerpt"][hit["start"]-hit["excerpt_start"]:hit["end"]-hit["excerpt_start"]]==hit["match"]
    with pytest.raises(ValueError,match="SHA"):
        extract(p,"bad")


def test_pq_hint_not_equipment():
    assert "pq_requirement" in matches("Проверить коэффициент мощности двигателя.")
    assert "pq_equipment" not in matches("Проверить коэффициент мощности двигателя.")
