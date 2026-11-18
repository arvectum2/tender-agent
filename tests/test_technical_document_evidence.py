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


def _unsupported_zip(entries, target):
    """Patch only selected local/central compression fields in synthetic ZIP."""
    import struct

    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w") as z:
        for name,content in entries:
            z.writestr(name,content)
    raw=bytearray(stream.getvalue())
    with zipfile.ZipFile(stream) as z:
        local_offset=z.getinfo(target).header_offset
        central=z.start_dir
    struct.pack_into("<H",raw,local_offset+8,9)
    while raw[central:central+4]==b"PK\x01\x02":
        n,x,c=struct.unpack_from("<HHH",raw,central+28)
        name=bytes(raw[central+46:central+46+n]).decode()
        if name==target:
            struct.pack_into("<H",raw,central+10,9)
            break
        central+=46+n+x+c
    return bytes(raw)


def test_unsupported_method_does_not_discard_supported_sibling(tmp_path):
    data=io.BytesIO()
    with zipfile.ZipFile(data,"w") as z:
        z.writestr("word/document.xml","<document><p><t>УКРМ</t></p></document>")
    p=tmp_path/"mixed.zip"
    p.write_bytes(_unsupported_zip([("bad.docx",data.getvalue()),("good.docx",data.getvalue())],"bad.docx"))
    before=p.read_bytes();result=extract(p,hashlib.sha256(before).hexdigest())
    assert result["status"]=="partial_review"
    assert [x["member"] for x in result["parts"]]==["good.docx"]
    assert result["review"]==[{"member":"bad.docx","reason":"unsupported ZIP compression or member feature","compression_method":9}]
    assert p.read_bytes()==before


def test_direct_unsupported_ooxml_marks_review(tmp_path):
    from scripts.research.run_technical_evidence import review_extract
    p=tmp_path/"bad.docx"
    p.write_bytes(_unsupported_zip([("word/document.xml",b"<document/>")],"word/document.xml"))
    result=review_extract(p,hashlib.sha256(p.read_bytes()).hexdigest())
    assert result["status"]=="review" and not result["parts"]
    assert "NotImplementedError" in result["review"][0]["reason"]
