"""Deterministic customer role-evidence resolution.

Generic synthetic fixtures only: no procurement numbers, no real tender data.
"""

from src.modules.tender_operator_agent_demo.customer_role_facts import (
    resolve_customer_name,
)


def value(**kwargs) -> str | None:
    resolution = resolve_customer_name(**kwargs)
    return resolution.value if resolution is not None else None


def test_organizer_fullname_first_customer_fullname_second():
    text = (
        "<notice>"
        "<organizer><fullName>МКУ Центр муниципальных закупок</fullName></organizer>"
        "<customer><fullName>МКУ Служба кладбищ</fullName></customer>"
        "</notice>"
    )

    assert value(notice_text=text) == "МКУ Служба кладбищ"


def test_organizer_fullname_only_resolves_nothing():
    text = "<notice><organizer><fullName>МКУ Центр муниципальных закупок</fullName></organizer></notice>"

    assert value(notice_text=text) is None


def test_supplier_fullname_does_not_beat_customer_fullname():
    text = (
        "<notice>"
        "<supplier><fullName>ООО Поставщик</fullName></supplier>"
        "<customer><fullName>МКУ Служба кладбищ</fullName></customer>"
        "</notice>"
    )

    assert value(notice_text=text) == "МКУ Служба кладбищ"


def test_direct_customer_name_tag():
    assert value(notice_text="<r><customerName>Customer Org</customerName></r>") == "Customer Org"


def test_explicit_customer_label_line():
    assert value(contract_draft_text="Заказчик: ООО «Ромашка»") == "ООО «Ромашка»"


def test_adjacent_line_table_like_customer():
    assert value(contract_draft_text="Заказчик\nООО «Ромашка»") == "ООО «Ромашка»"


def test_contract_preamble_single_line():
    source = "ООО «Ромашка», именуемое в дальнейшем «Заказчик», в лице директора, с одной стороны."

    assert value(contract_draft_text=source) == "ООО «Ромашка»"


def test_contract_preamble_multiline():
    source = (
        "Общество с ограниченной ответственностью «Ромашка»,\n"
        "именуемое в дальнейшем\n«Заказчик», в лице директора, с одной стороны."
    )

    assert value(contract_draft_text=source) == "Общество с ограниченной ответственностью «Ромашка»"


def test_supplier_preamble_before_customer_preamble():
    source = (
        "ООО «Поставщик», именуемое в дальнейшем «Поставщик», с одной стороны, и "
        "ООО «Ромашка», именуемое в дальнейшем «Заказчик», с другой стороны."
    )

    assert value(contract_draft_text=source) == "ООО «Ромашка»"


def test_bare_counterparty_roles_never_resolve():
    for role in ("Поставщик", "Исполнитель", "Подрядчик"):
        assert value(contract_draft_text=role) is None
        assert value(contract_draft_text=f"{role}:") is None


def test_role_only_value_after_customer_label_rejected():
    assert value(contract_draft_text="Заказчик: Поставщик") is None


def test_source_identity_surface_preserved():
    source = "Заказчик: ФГБУ «Центр-М» Минздрава России (г. Беслан)"

    assert value(contract_draft_text=source) == "ФГБУ «Центр-М» Минздрава России (г. Беслан)"


def test_generic_fullname_under_unknown_parent_resolves_nothing():
    text = "<data><party><fullName>Какая-то организация</fullName></party></data>"

    assert value(notice_text=text) is None


def test_two_distinct_explicit_customers_fail_closed():
    text = "Заказчик: ООО «Ромашка»\nЗаказчик: ООО «Василек»"

    assert value(contract_draft_text=text) is None


def test_possessive_customer_mentions_are_not_identity():
    text = "Требования заказчика к качеству.\nПоставка по заявке заказчика."

    assert value(contract_draft_text=text) is None


def test_verb_phrase_after_customer_role_is_not_identity():
    assert value(contract_draft_text="Заказчик направляет Заявки в пределах срока.") is None
    assert value(contract_draft_text="Заказчик обязуется принять товар.") is None


def test_v_dalnejshem_role_form():
    source = (
        "Федеральное государственное бюджетное учреждение «Центр», "
        "в дальнейшем по тексту «Заказчик», в лице директора."
    )

    assert value(contract_draft_text=source) == "Федеральное государственное бюджетное учреждение «Центр»"


def test_form_blanks_cannot_start_or_span_identity():
    source = (
        "г Беслан «__»____________20__ год "
        "Федеральное государственное бюджетное учреждение «Центр», "
        "в дальнейшем по тексту «Заказчик», в лице директора."
    )

    assert value(contract_draft_text=source) == "Федеральное государственное бюджетное учреждение «Центр»"


def test_preceding_sentence_does_not_leak_into_identity():
    source = (
        "Поставка товаров для нужд заказчика. "
        "ООО «Ромашка», именуемое в дальнейшем «Заказчик», приступает к работе."
    )

    assert value(contract_draft_text=source) == "ООО «Ромашка»"


def test_place_of_signing_header_is_not_part_of_identity():
    source = (
        "на поставку товаров\nр.п. Заречный\n"
        "ООО «Ромашка», именуемое в дальнейшем «Заказчик», приступает к работе."
    )

    assert value(contract_draft_text=source) == "ООО «Ромашка»"


def test_evidence_kind_outranks_source_role():
    # An explicit label in the lowest-priority combined text still outranks a
    # weaker contract-party preamble: kind first, source role breaks ties.
    assert (
        value(
            contract_draft_text="ООО «Ромашка», именуемое в дальнейшем «Заказчик».",
            combined_text="Заказчик: ООО «Василек»",
        )
        == "ООО «Василек»"
    )


def test_source_role_breaks_ties_within_same_kind():
    assert (
        value(
            contract_draft_text="ООО «Ромашка», именуемое в дальнейшем «Заказчик».",
            combined_text="ООО «Василек», именуемое в дальнейшем «Заказчик».",
        )
        == "ООО «Ромашка»"
    )
