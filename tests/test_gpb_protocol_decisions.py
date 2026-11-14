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


def test_marketing_group_and_tax_basis():
    raw = protocol(para("Начальная (максимальная) цена договора: 1 000,00 руб., без учета НДС.") +
                   para("Выбрать наиболее выгодные условия выполнения работ в заявке Группы лиц (ID Лидера - 123), которой присвоен первый порядковый номер, на сумму 900,00 руб., (без учета НДС)."))
    row = parse_protocol(raw)
    assert row["participant_role"] == "group_leader"
    assert row["best_bid_tax_basis"] == "excludes_vat"
    assert row["initial_price_tax_basis"] == "excludes_vat"
    assert row["best_bid_rub"] == "900.00"


def test_multiple_bid_amounts_not_guessed():
    raw = protocol(para("Начальная (максимальная) цена договора: 1 000,00 руб.") +
                   para("Определить лучшей заявку участника с идентификационным номером 123, на сумму 900,00 руб., на сумму 800,00 руб."))
    with pytest.raises(ValueError, match="ambiguous"):
        parse_protocol(raw)


def test_unsuccessful_not_a_winner():
    r = parse_protocol(protocol(para("Признать открытый конкурентный отбор несостоявшимся.")))
    assert r["decision"] == "PROCEDURE_DECLARED_UNSUCCESSFUL"
    assert r["participant_platform_id"] is None


def test_local_ordinal_does_not_become_platform_id():
    raw = protocol(para("Начальная (максимальная) цена договора:") +
                   para("100,00 без НДС;") + para("122,00 с НДС.") +
                   para("Комиссия приняла решение о выборе наиболее выгодных условий поставки товара в заявке Участника №2 с ценовым предложением (далее – Победитель):") +
                   para("90,00 руб. без НДС;") + para("109,80 руб. с НДС."))
    row = parse_protocol(raw)
    assert row["participant_local_ordinal"] == "2"
    assert row["participant_platform_id"] is None
    assert row["best_bid_rub"] == "109.80"
