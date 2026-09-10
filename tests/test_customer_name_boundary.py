"""Focused regression tests for customer_name extraction boundary cleanup.

When DOCX/table extraction places the next signature-party field on the same
logical line, the ``Заказчик:`` pattern may consume trailing role labels.
These tests verify that ``_extract_explicit_customer_name`` trims such
boundaries without corrupting legitimate organization names.
"""
from __future__ import annotations

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy


def test_real_regression_trailing_ispolnitel_boundary() -> None:
    """TEST A — exact real regression from calibration-44fz-0848300045426000620."""

    text = (
        'Заказчик: МУНИЦИПАЛЬНОЕ КАЗЕННОЕ УЧРЕЖДЕНИЕ "СЛУЖБА КЛАДБИЩ" '
        "ОДИНЦОВСКОГО ГОРОДСКОГО ОКРУГА МОСКОВСКОЙ ОБЛАСТИ "
        "Исполнитель:________________"
    )

    result = legacy._extract_customer_name_from_text(text)

    assert result == (
        'МУНИЦИПАЛЬНОЕ КАЗЕННОЕ УЧРЕЖДЕНИЕ "СЛУЖБА КЛАДБИЩ" '
        "ОДИНЦОВСКОГО ГОРОДСКОГО ОКРУГА МОСКОВСКОЙ ОБЛАСТИ"
    )


def test_postavshchik_boundary_same_line() -> None:
    """TEST B — same-line Поставщик boundary."""

    text = 'Заказчик: ООО "Альфа" Поставщик: ООО "Бета"'

    result = legacy._extract_customer_name_from_text(text)

    assert result == 'ООО "Альфа"'


def test_podryadchik_boundary_same_line() -> None:
    """TEST C — same-line Подрядчик boundary."""

    text = 'Заказчик: ЗАО "Гамма" Подрядчик: ЗАО "Дельта"'

    result = legacy._extract_customer_name_from_text(text)

    assert result == 'ЗАО "Гамма"'


def test_no_false_truncation_organization_name_with_ispolnitel() -> None:
    """TEST D — organization name containing Исполнитель must not be truncated."""

    text = 'Заказчик: ООО "Исполнитель Сервис"'

    result = legacy._extract_customer_name_from_text(text)

    assert result == 'ООО "Исполнитель Сервис"'


def test_xml_customer_block_extraction_unchanged() -> None:
    """TEST E — XML <customer> block extraction continues working."""

    source = """
    <notice>
      <organizer><fullName>МКУ Центр муниципальных закупок</fullName></organizer>
      <customer><fullName>МКУ Служба кладбищ</fullName></customer>
    </notice>
    """

    result = legacy._extract_customer_name_from_text(source)

    assert result == "МКУ Служба кладбищ"


def test_named_contract_party_pattern_unchanged() -> None:
    """TEST F — «именуемое ... «Заказчик»» pattern continues working."""

    source = (
        'МУНИЦИПАЛЬНОЕ КАЗЕННОЕ УЧРЕЖДЕНИЕ "СЛУЖБА КЛАДБИЩ", '
        'именуемое в дальнейшем «Заказчик», в лице директора, с одной стороны.'
    )

    result = legacy._extract_customer_name_from_text(source)

    assert result == 'МУНИЦИПАЛЬНОЕ КАЗЕННОЕ УЧРЕЖДЕНИЕ "СЛУЖБА КЛАДБИЩ"'


def test_customer_name_tag_extraction_unchanged() -> None:
    """TEST G — <customerName> tag extraction continues working."""

    source = "<notice><customerName>ООО Рога и Копыта</customerName></notice>"

    result = legacy._extract_customer_name_from_text(source)

    assert result == "ООО Рога и Копыта"


def test_empty_input_returns_none() -> None:
    """TEST H — empty/None input returns None."""

    assert legacy._extract_customer_name_from_text(None) is None
    assert legacy._extract_customer_name_from_text("") is None
    assert legacy._extract_customer_name_from_text("   ") is None
