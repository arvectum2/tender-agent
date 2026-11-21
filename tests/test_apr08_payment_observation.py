import pytest

from src.modules.tender_operator_agent_demo.evidence_payment_observation import (
    literal_payment_observation,
    payment_candidate,
)

CLAUSE = ('3.6. Оплата оказанных услуг производится в течение 7 (семи) рабочих дней с даты подписания документа о приемке '
          'и предоставления документов. Заказчик не несет ответственности за задержку при нарушении срока оформления документов.')


def test_literal_duration_and_full_qualifiers():
    result = literal_payment_observation(CLAUSE)
    assert result['mentioned_days'] == 7 and result['day_unit'] == 'WORKING_DAYS'
    assert 'и предоставления документов' in result['following_context_literal']
    assert 'не несет ответственности' in result['following_context_literal']
    assert result['effective_due_date'] is None and not result['trigger_sufficiency_verified'] and not result['exceptions_exhaustively_checked']
    assert payment_candidate(CLAUSE, set(), object_kind='services') == (1, CLAUSE)
    assert payment_candidate(CLAUSE, set(), object_kind='works') is None
    assert payment_candidate(CLAUSE + '\n' + CLAUSE.replace('7 (семи)', '5 (пяти)'), set()) is None


@pytest.mark.parametrize('text', [
    'Оплата производится в течение 7 (пяти) рабочих дней с даты приемки.',
    'Оплата не производится в течение 7 рабочих дней с даты приемки.',
    'Оплата производится в течение 7 дней с даты приемки.',
    'Оплата производится в течение 7 рабочих дней.',
    'Оплата производится в течение 7 рабочих дней с даты приемки или 10 календарных дней.',
    'Оплата производится в течение 7 рабочих дней с даты приемки',
    'Исполнитель выставляет счет в течение 7 рабочих дней с даты приемки.',
    'Оплата производится в течение 7 рабочих дней после приемки. Срок поставки 30 календарных дней.',
])
def test_incomplete_ambiguous_or_unsupported_clause_abstains(text):
    assert literal_payment_observation(text) is None


def test_calendar_days_are_not_working_days():
    result = literal_payment_observation('Оплата работ производится в течение 10 календарных дней со дня приемки.')
    assert result['mentioned_days'] == 10 and result['day_unit'] == 'CALENDAR_DAYS'
