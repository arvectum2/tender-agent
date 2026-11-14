import io
import zipfile

import pytest

from scripts.research.read_gpb_protocol_decisions import parse_protocol


def protocol(text):
    doc = io.BytesIO()
    with zipfile.ZipFile(doc, "w") as z:
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + text + "</w:body></w:document>")
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as z:
        z.writestr("protocol.docx", doc.getvalue())
    return arc.getvalue()


def para(text):
    return "<w:p><w:r><w:t>" + text + "</w:t></w:r></w:p>"


def test_best_bid_not_signed_contract():
    raw = protocol(para("Начальная (максимальная) цена договора: 1 000,00 руб.") +
                   para("Определить лучшей заявку участника с идентификационным номером 123, на сумму 900,00 руб."))
    r = parse_protocol(raw)
    assert r["best_bid_rub"] == "900.00"
    assert r["initial_price_rub"] == "1000.00"
    assert r["participant_platform_id"] == "123"
    assert r["participant_legal_identity"] is None
    assert r["contract_amount"] is None


def test_no_explicit_decision_requires_review():
    with pytest.raises(ValueError, match="absent"):
        parse_protocol(protocol(para("Признать участника соответствующим требованиям.")))
