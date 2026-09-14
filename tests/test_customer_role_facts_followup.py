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


def test_numbered_notice_customer_table_row_with_name_field_is_resolved():
    source = (
        "6\tЗаказчик\tНаименование: ГОСУДАРСТВЕННОЕ БЮДЖЕТНОЕ УЧРЕЖДЕНИЕ ''ЦЕНТР''"
        "Место нахождения и почтовый адрес: Российская Федерация, г. Москва"
        "Адрес электронной почты: office@example.test"
    )

    resolution = resolve_customer_name(notice_text=source)

    assert resolution is not None
    assert resolution.value == "ГОСУДАРСТВЕННОЕ БЮДЖЕТНОЕ УЧРЕЖДЕНИЕ ''ЦЕНТР''"
    assert resolution.evidence_kind == "explicit_customer_label"
    assert resolution.source_role == "notice"


def test_unnumbered_notice_customer_table_row_is_resolved():
    source = "Заказчик\tНаименование: Государственное учреждение «Центр»Почтовый адрес: г. Москва"

    assert value(notice_text=source) == "Государственное учреждение «Центр»"


def test_unquoted_customer_role_in_contract_preamble_is_resolved():
    source = (
        "Государственное учреждение «Центр», "
        "именуемое в дальнейшем Заказчик, в лице директора."
    )

    resolution = resolve_customer_name(contract_draft_text=source)

    assert resolution is not None
    assert resolution.value == "Государственное учреждение «Центр»"
    assert resolution.evidence_kind == "contract_party_preamble"
    assert resolution.source_role == "contract"


def test_notice_table_customer_outranks_unquoted_contract_preamble():
    notice = "6\tЗаказчик\tНаименование: ГОСУДАРСТВЕННОЕ УЧРЕЖДЕНИЕ ''ЦЕНТР''Почтовый адрес: г. Москва"
    contract = (
        "Государственное учреждение «Центр», "
        "именуемое в дальнейшем Заказчик, в лице директора."
    )

    resolution = resolve_customer_name(notice_text=notice, contract_draft_text=contract)

    assert resolution is not None
    assert resolution.value == "ГОСУДАРСТВЕННОЕ УЧРЕЖДЕНИЕ ''ЦЕНТР''"
    assert resolution.evidence_kind == "explicit_customer_label"
    assert resolution.source_role == "notice"


def test_inflected_unquoted_customer_word_is_not_a_role_assignment():
    source = (
        "Государственное учреждение «Центр», "
        "именуемое в дальнейшем Заказчиком, в лице директора."
    )

    assert value(contract_draft_text=source) is None


def test_source_authored_nested_guillemets_with_missing_outer_closer_are_preserved():
    source = 'Заказчик: Государственное учреждение «Центр помощи детям «Солнечный»'

    assert value(supporting_texts=[source]) == 'Государственное учреждение «Центр помощи детям «Солнечный»'


def test_dangling_open_quote_without_closing_boundary_is_rejected():
    source = 'Заказчик: Государственное учреждение «Центр'

    assert value(supporting_texts=[source]) is None


def test_public_customer_acting_on_behalf_of_region_preserves_legal_entity_identity():
    source = (
        "Государственное казенное учреждение области «Центр», "
        "от имени области, именуемое в дальнейшем «Заказчик», в лице директора."
    )

    resolution = resolve_customer_name(contract_draft_text=source)

    assert resolution is not None
    assert resolution.value == "Государственное казенное учреждение области «Центр»"
    assert resolution.evidence_kind == "contract_party_preamble"
    assert resolution.source_role == "contract"
