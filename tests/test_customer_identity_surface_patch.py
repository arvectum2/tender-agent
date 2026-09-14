"""Regression coverage for legal-name vs definitional-alias boundaries."""

from src.modules.tender_operator_agent_demo.customer_role_facts import (
    resolve_customer_name,
)


def value(**kwargs) -> str | None:
    resolution = resolve_customer_name(**kwargs)
    return resolution.value if resolution is not None else None


def test_contract_preamble_trims_trailing_dalee_short_form():
    source = (
        'Муниципальное бюджетное учреждение "Школа Радуга" '
        '(далее - МБУ "Школа Радуга"), именуемое в дальнейшем «Заказчик»'
    )

    assert value(contract_draft_text=source) == 'Муниципальное бюджетное учреждение "Школа Радуга"'


def test_explicit_customer_label_trims_trailing_dalee_short_form():
    source = (
        'Заказчик: Муниципальное бюджетное учреждение "Школа Радуга" '
        '(далее — МБУ "Школа Радуга")'
    )

    assert value(supporting_texts=[source]) == 'Муниципальное бюджетное учреждение "Школа Радуга"'


def test_v_dalneishem_alias_variant_is_trimmed():
    source = (
        'Государственное учреждение «Центр» '
        '(в дальнейшем по тексту: ГУ «Центр»), именуемое в дальнейшем «Заказчик»'
    )

    assert value(contract_draft_text=source) == 'Государственное учреждение «Центр»'


def test_ordinary_legal_parenthetical_is_preserved():
    source = (
        'Государственное учреждение «Центр» (филиал № 1), '
        'именуемое в дальнейшем «Заказчик»'
    )

    assert value(contract_draft_text=source) == 'Государственное учреждение «Центр» (филиал № 1)'


def test_defined_abbreviation_without_parentheses_is_not_rewritten():
    source = 'Заказчик: Государственное учреждение «Центр» — ГУ «Центр»'

    assert value(supporting_texts=[source]) == 'Государственное учреждение «Центр» — ГУ «Центр»'


def test_alias_variant_does_not_create_equal_strength_false_conflict():
    plain = 'Заказчик: Государственное учреждение «Центр»'
    aliased = 'Заказчик: Государственное учреждение «Центр» (далее - ГУ «Центр»)'

    assert value(supporting_texts=[plain, aliased]) == 'Государственное учреждение «Центр»'
