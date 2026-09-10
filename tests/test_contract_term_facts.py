from __future__ import annotations

from pathlib import Path

import pytest

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
    assert facts["performance_security_percent"].value == 10
    assert type(facts["performance_security_percent"].value) is int
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
    assert facts["performance_security_percent"].value == 10
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


def test_extracts_execution_and_warranty_terms_with_source_roles() -> None:
    facts, conflicts = extract_contract_term_facts(
        [
            _document(
                "Срок начала оказания услуг Исполнителем**: 0 дн. от даты заключения контракта;"
                "Срок окончания оказания услуг Исполнителем**: 30.11.2026 (МСК);\n"
                "Дата окончания исполнения контракта\t23.12.2026 (МСК)\n"
                "Требуется обеспечение исполнения обязательств по предоставленной гарантии качества "
                "товаров, работ, услуг\tНет"
            ),
            _document(
                "Место оказания услуг: Московская область, г. Одинцово, ул. Молодёжная д. 18, помещение 3/3.\n"
                "Срок, на который предоставляется гарантия и (или) требования к объему предоставления "
                "гарантий качества товара, работы, услуги — 12 месяцев с даты приёмки оказанных услуг.",
                role="technical_spec",
                name="Техническое задание.docx",
            ),
        ]
    )

    assert conflicts == []
    assert {field: facts[field].value for field in (
        "service_start", "service_deadline", "contract_end_date", "performance_place", "warranty_term", "warranty_security_required"
    )} == {
        "service_start": "0 дн. от даты заключения контракта",
        "service_deadline": "30.11.2026 (МСК)",
        "contract_end_date": "23.12.2026 (МСК)",
        "performance_place": "Московская область, г. Одинцово, ул. Молодёжная д. 18, помещение 3/3.",
        "warranty_term": "12 месяцев с даты приёмки оказанных услуг",
        "warranty_security_required": False,
    }
    assert facts["performance_place"].source_document == "Техническое задание.docx"
    assert facts["service_start"].source_document == "Проект контракта.docx"


def test_execution_and_warranty_terms_do_not_fabricate_or_match_wrong_semantics() -> None:
    facts, _ = extract_contract_term_facts(
        [
            _document(
                "Дата публикации извещения: 30.11.2026.\n"
                "Срок подачи заявок: 23.12.2026.\n"
                "Обеспечение исполнения контракта: 10%.\n"
                "Обеспечение заявки: 1%.\n"
                "Гарантия предоставляется в соответствии с контрактом.\n"
                "Срок оказания услуг: 30.11.2026."
            ),
            _document(
                "Адрес заказчика: Московская область, г. Одинцово.\n"
                "Гарантия предоставляется без указания срока.",
                role="technical_spec",
                name="Техническое задание.docx",
            ),
        ]
    )

    assert set(facts).isdisjoint({
        "service_start", "service_deadline", "contract_end_date", "performance_place", "warranty_term", "warranty_security_required"
    })


@pytest.mark.parametrize(
    ("field", "first", "second", "role"),
    [
        (
            "service_start",
            "Срок начала оказания услуг Исполнителем: 0 дн. от даты заключения контракта;Срок окончания оказания услуг Исполнителем: 30.11.2026 (МСК);",
            "Срок начала оказания услуг Исполнителем: 1 дн. от даты заключения контракта;Срок окончания оказания услуг Исполнителем: 30.11.2026 (МСК);",
            "contract_draft",
        ),
        (
            "service_deadline",
            "Срок начала оказания услуг Исполнителем: 0 дн. от даты заключения контракта;Срок окончания оказания услуг Исполнителем: 30.11.2026 (МСК);",
            "Срок начала оказания услуг Исполнителем: 0 дн. от даты заключения контракта;Срок окончания оказания услуг Исполнителем: 01.12.2026 (МСК);",
            "contract_draft",
        ),
        ("contract_end_date", "Дата окончания исполнения контракта | 30.11.2026 (МСК)", "Дата окончания исполнения контракта | 01.12.2026 (МСК)", "contract_draft"),
        ("performance_place", "Место оказания услуг: г. Одинцово.", "Место оказания услуг: г. Москва.", "technical_spec"),
        ("warranty_term", "Срок, на который предоставляется гарантия — 12 месяцев с даты приёмки оказанных услуг.", "Срок, на который предоставляется гарантия — 24 месяцев с даты приёмки оказанных услуг.", "technical_spec"),
        ("warranty_security_required", "Требуется обеспечение исполнения обязательств по предоставленной гарантии качества товаров, работ, услуг | Нет", "Требуется обеспечение исполнения обязательств по предоставленной гарантии качества товаров, работ, услуг | Да", "contract_draft"),
    ],
)
def test_conflicting_execution_and_warranty_terms_fail_closed(field: str, first: str, second: str, role: str) -> None:
    facts, conflicts = extract_contract_term_facts(
        [_document(first, role=role, name="Первый.docx"), _document(second, role=role, name="Второй.docx")]
    )

    assert field not in facts
    assert field in conflicts


def test_execution_and_warranty_terms_do_not_leak_from_non_eligible_roles() -> None:
    facts, _ = extract_contract_term_facts(
        [
            _document(
                "Срок начала оказания услуг Исполнителем: 0 дн. от даты заключения контракта;"
                "Срок окончания оказания услуг Исполнителем: 30.11.2026 (МСК);\n"
                "Дата окончания исполнения контракта | 23.12.2026 (МСК)\n"
                "Требуется обеспечение исполнения обязательств по предоставленной гарантии качества товаров, работ, услуг | Нет\n"
                "Место оказания услуг: г. Одинцово.\n"
                "Срок, на который предоставляется гарантия — 12 месяцев с даты приёмки оказанных услуг.",
                role="supporting",
            )
        ]
    )

    assert set(facts).isdisjoint({
        "service_start", "service_deadline", "contract_end_date", "performance_place", "warranty_term", "warranty_security_required"
    })
