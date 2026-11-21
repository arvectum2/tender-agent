import pytest

from src.modules.tender_operator_agent_demo.evidence_delivery_observation import (
    delivery_candidate,
    literal_delivery_observation,
)

CLAUSE = '1.4. Срок оказания услуг: с момента заключения Контракта по 07.12.2026 г. (включительно).'


def test_explicit_service_date_preserves_context():
    obs = literal_delivery_observation(CLAUSE, object_kind='services')
    assert obs['mentioned_date'] == '2026-12-07'
    assert obs['trigger_literal'] == 'с момента заключения Контракта'
    assert obs['boundary_literal'] == 'по' and obs['explicit_inclusive'] is True
    assert obs['effective_due_date'] is None and not obs['trigger_sufficiency_verified']
    assert 'включительно' in obs['term_literal'] and not obs['exceptions_exhaustively_checked']
    for kind in ('works', 'goods', 'contract'):
        assert literal_delivery_observation(CLAUSE, object_kind=kind) is None


def test_relative_explicit_days_and_absolute_contract_execution():
    obs = literal_delivery_observation('Срок поставки товара: в течение 10 календарных дней с даты получения заявки заказчика.', object_kind='goods')
    assert obs['mentioned_days'] == 10 and obs['day_unit'] == 'CALENDAR_DAYS'
    assert obs['trigger_literal'] == 'с даты получения заявки заказчика' and obs['mentioned_date'] is None
    obs = literal_delivery_observation('Срок исполнения контракта - 31.12.2027 г.', object_kind='contract')
    assert obs['mentioned_date'] == '2027-12-31' and obs['explicit_inclusive'] is None
    assert obs['effective_due_date'] is None


@pytest.mark.parametrize('text', [
    'Срок оказания услуг: до 31.02.2026 г.',
    'Срок оказания услуг: до 07.12.2026 г. при условии оплаты.',
    'Срок оказания услуг: в течение 10 дней с даты заключения контракта.',
    'Срок оказания услуг: до 07.12.2026 г. или до 08.12.2026 г.',
    'Срок действия контракта: до 07.12.2026 г.',
    'Срок оплаты услуг: до 07.12.2026 г.',
    'Сроки оказания услуг по Контракту установлены в п. 1.6. Описания объекта закупки.',
    'Срок оказания услуг: до 07.12.2026 г.\x00',
])
def test_unsupported_or_invalid_date_never_inferred(text):
    assert literal_delivery_observation(text, object_kind='services') is None


def test_identical_terms_may_be_sampled_but_contradictory_lines_abstain():
    same = CLAUSE.replace('1.4. Срок', '1.5. Сроки')
    assert delivery_candidate(CLAUSE + '\n' + same, set(), object_kind='services') == (1, CLAUSE)
    assert delivery_candidate(CLAUSE + '\n' + same.replace('07.12', '08.12'), set(), object_kind='services') is None
