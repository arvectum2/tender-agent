from __future__ import annotations

from pathlib import Path

from src.modules.procurement_analysis.frozen_types import AnalyzedDocument
from src.modules.tender_operator_agent_demo.contract_term_facts import (
    extract_contract_term_facts,
)


def _document(text: str, *, role: str = "contract_draft", name: str = "Проект контракта.docx") -> AnalyzedDocument:
    return AnalyzedDocument(
        display_name=name,
        extension=Path(name).suffix.lower(),
        role=role,
        text=text,
        extracted_text_available=True,
        warnings=[],
        source="test",
        file_id=f"FILE-{name}",
    )


def test_extracts_explicit_contract_terms_with_provenance() -> None:
    facts, conflicts = extract_contract_term_facts(
        [
            _document(
                "Оплата | 100% По фактическому объёму. Срок исполнения обязательства Заказчиком: "
                "5 раб. дн. от даты подписания документа-предшественника «Документ о приемке (функция ДОП)».\n"
                "Выплата аванса не предусмотрена.\n"
                "Размер обеспечения исполнения контракта, % от НМЦК | 10\n"
                "Исполнитель: 5 раб. дн. от даты окончания исполнения обязательства. "
                "Заказчик: 5 раб. дн. от даты получения документа."
            )
        ]
    )

    assert conflicts == []
    assert facts["payment_terms"].value == {
        "payment": "100% По фактическому объёму",
        "deadline": "5 раб. дн. от даты подписания документа-предшественника «Документ о приемке (функция ДОП)»",
    }
    assert facts["advance_payment"].value is False
    assert facts["performance_security_percent"].value == 10.0
    assert facts["acceptance_terms"].value == {
        "executor_submission": "5 раб. дн. от даты окончания исполнения обязательства",
        "customer_acceptance": "5 раб. дн. от даты получения документа",
    }
    assert facts["payment_terms"].source_document == "Проект контракта.docx"
    assert facts["payment_terms"].locator == "line:1"


def test_extracts_contract_table_terms_without_table_labels_in_values() -> None:
    facts, conflicts = extract_contract_term_facts(
        [
            _document(
                "Оплата за услуги\tОплата\t100% По фактическому объёму\n"
                "Срок исполнения обязательства Заказчиком** 5 раб. дн. от даты подписания "
                "документа-предшественника «Документ о приемке (функция ДОП)» (описание закупки);\n"
                "Размер обеспечения исполнения контракта, % от НМЦК\tСумма\n"
                "10\t1000\n"
                "Услуги\tДокумент о приемке\t5 раб. дн. от даты окончания исполнения обязательства "
                "в данном документе\tПодписание\tИсполнитель\n"
                "*\t5 раб. дн. от даты получения документа\tПодписание\tЗаказчик"
            )
        ]
    )

    assert conflicts == []
    assert facts["payment_terms"].value["deadline"] == (
        "5 раб. дн. от даты подписания документа-предшественника «Документ о приемке (функция ДОП)»"
    )
    assert facts["performance_security_percent"].value == 10.0
    assert facts["acceptance_terms"].value == {
        "executor_submission": "5 раб. дн. от даты окончания исполнения обязательства",
        "customer_acceptance": "5 раб. дн. от даты получения документа",
    }


def test_absent_terms_do_not_fabricate_facts() -> None:
    facts, conflicts = extract_contract_term_facts([_document("Цена контракта является твердой.")])

    assert facts == {}
    assert conflicts == []


def test_wrong_security_and_generic_acceptance_do_not_match() -> None:
    facts, _ = extract_contract_term_facts(
        [
            _document(
                "Размер обеспечения заявки, % от НМЦК | 1\n"
                "Размер обеспечения гарантийных обязательств, % от НМЦК | 5\n"
                "Приемка осуществляется в соответствии с контрактом."
            )
        ]
    )

    assert "performance_security_percent" not in facts
    assert "acceptance_terms" not in facts


def test_non_contract_document_does_not_leak_terms() -> None:
    facts, conflicts = extract_contract_term_facts(
        [_document("Выплата аванса не предусмотрена.", role="technical_spec")]
    )

    assert facts == {}
    assert conflicts == []


def test_conflicting_contract_documents_fail_closed() -> None:
    facts, conflicts = extract_contract_term_facts(
        [
            _document("Выплата аванса не предусмотрена.", name="Проект 1.docx"),
            _document("Выплата аванса предусмотрена 10%.", name="Проект 2.docx"),
        ]
    )

    assert "advance_payment" not in facts
    assert conflicts == ["advance_payment"]


def test_postpayment_is_not_advance_payment() -> None:
    facts, _ = extract_contract_term_facts(
        [_document("Оплата производится после приемки оказанных услуг в течение 7 рабочих дней.")]
    )

    assert "advance_payment" not in facts
