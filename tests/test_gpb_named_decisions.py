import pytest

from scripts.research.persist_gpb_protocol_decisions import attach_decision
from scripts.research.read_gpb_named_decisions import named_lines

HEADER="Протокол № 340/ТГК/КО заседания Комиссии (в части подведения итогов открытого конкурентного отбора в электронной форме № 2133/КО)"
INITIAL="Начальная (максимальная) цена договора: 100 000,00 руб., без учета НДС."
WIN="3) Определить лучшей заявку ООО «Тест» (123423, г. Москва, ул. Примерная, д. 1), на сумму 90 000,00 руб., (без учета НДС), в соответствии с документацией о конкурентном отборе в электронной форме № 2133/КО."
TITLE="32414136828 Тендер на закупку КО №2133/КО - Оборудование | ЭТП ГПБ"


def test_named_exact_procedure_identity_and_tax():
    r=named_lines([HEADER,INITIAL,WIN],"protocol.docx","a"*64,TITLE)
    assert r["participant_name_as_published"]=="ООО «Тест»"
    assert r["participant_legal_identity"] is None and r["contract_amount"] is None
    assert r["protocol_procedure_reference"]=="2133/КО"
    assert r["best_bid_rub"]=="90000.00" and r["best_bid_tax_basis"]=="excludes_vat"
    assert r["initial_price_rub"]=="100000.00"
    assert r["best_bid_evidence"]==WIN


def test_no_wrong_or_ambiguous_identity_or_price():
    for title in (TITLE.replace("2133/КО","21330/КО"),TITLE.replace("2133/КО","2133/МИ")):
        with pytest.raises(ValueError,match="number"):
            named_lines([HEADER,INITIAL,WIN],None,"a"*64,title)
    with pytest.raises(ValueError):
        named_lines([HEADER,INITIAL,WIN,WIN],None,"a"*64,TITLE)
    with pytest.raises(ValueError):
        named_lines([HEADER,INITIAL,WIN.replace("№ 2133/КО","№ 9999/КО")],None,"a"*64,TITLE)
    with pytest.raises(ValueError):
        named_lines([HEADER,INITIAL,WIN+" на сумму 100,00 руб."],None,"a"*64,TITLE)


def test_named_storage_no_verified_inn_or_signed_contract():
    r=named_lines([HEADER,INITIAL,WIN],None,"a"*64,TITLE)
    r.update(external_id="etp:1",protocol_sha256="b"*64,document_url="u")
    m={"source":"etp_gpb","capture_receipts":[{"external_id":"etp:1","sha256":"b"*64,"document_url":"u","document_role":"published_protocol"}]}
    assert attach_decision(m,r)["protocol_decision"]==r
    with pytest.raises(ValueError):
        attach_decision(m,r|{"participant_legal_identity":{"inn":"1234567890"}})
    with pytest.raises(ValueError):
        attach_decision(m,r|{"participant_address_as_published":""})
