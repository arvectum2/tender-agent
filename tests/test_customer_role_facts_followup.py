"""Follow-up regression coverage for customer role identity boundaries."""

from src.modules.tender_operator_agent_demo.customer_role_facts import (
    resolve_customer_name,
)


def value(**kwargs) -> str | None:
    resolution = resolve_customer_name(**kwargs)
    return resolution.value if resolution is not None else None


def test_plural_customer_label_same_line():
    source = 'Заказчик(и): ГОСУДАРСТВЕННОЕ УЧРЕЖДЕНИЕ "ЦЕНТР"'

    assert value(supporting_texts=[source]) == 'ГОСУДАРСТВЕННОЕ УЧРЕЖДЕНИЕ "ЦЕНТР"'


def test_plural_customer_label_adjacent_line():
    source = 'Заказчик(и):\nГОСУДАРСТВЕННОЕ УЧРЕЖДЕНИЕ "ЦЕНТР"'

    assert value(supporting_texts=[source]) == 'ГОСУДАРСТВЕННОЕ УЧРЕЖДЕНИЕ "ЦЕНТР"'


def test_plural_protocol_label_outranks_contract_preamble():
    contract = (
        'Государственное учреждение «Центр», '
        'именуемое в дальнейшем «Заказчик», в лице директора.'
    )
    protocol = 'Заказчик(и):\nГОСУДАРСТВЕННОЕ УЧРЕЖДЕНИЕ "ЦЕНТР"'

    resolution = resolve_customer_name(
        contract_draft_text=contract,
        supporting_texts=[protocol],
    )

    assert resolution is not None
    assert resolution.value == 'ГОСУДАРСТВЕННОЕ УЧРЕЖДЕНИЕ "ЦЕНТР"'
    assert resolution.evidence_kind == "explicit_customer_label"
    assert resolution.source_role == "supporting"


def test_year_suffix_before_preamble_is_not_a_locality_prefix():
    source = (
        'Идентификационный код закупки 2026 г. '
        'Государственное учреждение «Центр», '
        'именуемое в дальнейшем «Заказчик», в лице директора.'
    )

    assert value(contract_draft_text=source) == 'Государственное учреждение «Центр»'


def test_unbalanced_explicit_identity_is_rejected():
    source = 'Заказчик: ГУ «Центр)'

    assert value(contract_draft_text=source) is None


def test_unbalanced_parenthetical_preamble_fragment_is_rejected():
    source = 'ГУ «Центр), именуемое в дальнейшем «Заказчик», в лице директора.'

    assert value(contract_draft_text=source) is None
