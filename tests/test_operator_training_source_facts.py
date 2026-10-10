"""Training-source candidate extraction contracts, independent of report formatting."""

from __future__ import annotations

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_training_source_facts import (
    TrainingCandidateFacts,
    extract_training_candidate_facts,
)


def extract(*, metadata=None, spec="", contract="", notice="", price=None):
    return extract_training_candidate_facts(
        metadata or {},
        spec,
        contract,
        notice,
        _match_first=legacy._match_first,
        _extract_notice_service_deadline=legacy._extract_notice_service_deadline,
        _cleanup_tabular_value=legacy._cleanup_tabular_value,
        _extract_notice_price=(lambda *_: price),
        _match_first_dotall=legacy._match_first_dotall,
    )


def test_unknown_training_fields_are_not_invented_without_documents():
    facts = extract(metadata={"tender_title": "Образовательные услуги"})
    assert isinstance(facts, TrainingCandidateFacts)
    assert facts.service_subject == "Образовательные услуги"
    assert facts.training_format is None
    assert facts.hours is None
    assert facts.listeners is None
    assert facts.service_deadline is None
    assert facts.location is None
    assert facts.initial_price is None
    assert facts.payment_terms is None
    assert facts.execution_security is None
    assert facts.execution_security_percent is None
    assert facts.execution_security_amount is None
    assert facts.acceptance_window is None
    assert facts.unilateral_termination is None


def test_training_details_are_only_taken_from_supplied_source():
    spec = (
        "Объект закупки: Подготовка специалистов\n"
        "Форма обучения: Очно-заочная\n"
        "72 часа, 15 человек\n"
        "Окончание не позднее 15 декабря 2026 года\n"
        "3. Место оказания услуг: г. Казань\n"
        "4. Требования к аттестации\n"
    )
    facts = extract(spec=spec)
    assert facts.service_subject == "Подготовка специалистов"
    assert facts.training_format is not None and "Очно-заочная" in facts.training_format
    assert facts.hours is not None and "72" in facts.hours
    assert facts.listeners == "15"
    assert facts.service_deadline is not None and "15 декабря 2026" in facts.service_deadline
    assert facts.location is not None and "Казань" in facts.location
    assert facts.initial_price is None


def test_security_percent_depends_on_actual_contract_text():
    without_contract = extract()
    with_contract = extract(contract="Обеспечение исполнения контракта составляет 5% от НМЦК.")
    assert without_contract.execution_security_percent is None
    assert with_contract.execution_security_percent == "5"
    assert with_contract.execution_security is not None


def test_notice_price_dependency_is_not_replaced_by_inferred_cost():
    fact = extract(metadata={"tender_title": "Курсы"}, price="540 000")
    assert fact.initial_price == "540 000"
    assert fact.hours is None
    assert fact.listeners is None


def test_training_fact_extractor_keeps_original_named_tuple_field_order():
    facts = extract()
    assert len(facts) == 13
    assert facts._fields[0] == "service_subject"
    assert facts._fields[-1] == "unilateral_termination"

def test_source_location_before_unnumbered_paragraph_is_preserved():
    spec = (
        "3. Место оказания услуг: очное обучение в городе Хабаровске; "
        "дистанционная часть на территории Заказчика.\n"
        "Услуги должны быть согласованы с ФСТЭК.\n"
    )
    facts = extract(spec=spec)
    assert facts.location is not None
    assert "городе Хабаровске" in facts.location
    assert "Услуги должны" not in facts.location


def test_source_city_on_next_line_and_unrelated_paragraph_not_conflated():
    spec = (
        "Место оказания Услуг:\n"
        "г. Казань, ул. Центральная, 7\n"
        "Дополнительно проводится аттестация.\n"
    )
    facts = extract(spec=spec)
    assert facts.location == "г. Казань, ул. Центральная, 7"
