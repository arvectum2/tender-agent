"""Direct product parsers and frozen legacy entrypoints agree on provenance."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo import (
    operator_supply_source_parsers as parsed,
)
from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy


def _invoke_direct(func, text: str, filename: str):
    dependencies = {}
    for name in inspect.signature(func).parameters:
        if name in {"text", "source_document"}:
            continue
        dependencies[name] = (
            legacy.SupplyItem
            if name == "supply_item_type"
            else legacy._SUPPLY_UNIT_PATTERN
            if name == "supply_unit_pattern"
            else getattr(legacy, name)
        )
    return func(text, filename, **dependencies)


@pytest.mark.parametrize(
    ("direct", "facade", "source", "filename"),
    [
        (
            parsed.extract_supply_items_from_spec_text,
            legacy._extract_supply_items_from_spec_text,
            "",
            "Техническое задание.docx",
        ),
        (
            parsed.extract_service_items_from_nmck_text,
            legacy._extract_service_items_from_nmck_text,
            (
                "Диагностика тормозной системы\\tУсловная единица\\t1 900,00\\n"
                "Итого\\t\\t500 000,00"
            ),
            "НМЦК.docx",
        ),
        (
            parsed.extract_supply_items_from_notification_xml,
            legacy._extract_supply_items_from_notification_xml,
            (
                "<root><purchaseObject><name>Кабель силовой</name>"
                "<price>10.50</price><quantity>5</quantity>"
                "<sum>52.50</sum></purchaseObject></root>"
            ),
            "notice.xml",
        ),
        (
            parsed.extract_supply_items_from_notification_xml,
            legacy._extract_supply_items_from_notification_xml,
            "<root><purchaseObject>",
            "notice.xml",
        ),
    ],
)
def test_candidate_sources_identical_with_legacy_facade(
    direct, facade, source, filename
):
    baseline = facade(source, filename)
    candidates = _invoke_direct(direct, source, filename)
    assert candidates == baseline
    assert all(type(item) is legacy.SupplyItem for item in candidates)
    assert all(item.source_document == filename for item in candidates)
    assert all(item.evidence_id for item in candidates)


def test_service_source_fixture_preserves_all_source_rows_and_missing_volumes():
    text = Path(
        "tests/fixtures/golden/0352300080626000109/nmck_services_excerpt.txt"
    ).read_text()
    items = _invoke_direct(
        parsed.extract_service_items_from_nmck_text, text, "nmck_services.docx"
    )
    assert len(items) >= 41
    assert all(
        item.quantity is None and item.quantity_status == "not_specified"
        for item in items
    )
    assert all(
        item.source_kind == "nmck_service_table" and item.raw_fragment for item in items
    )
    assert items == legacy._extract_service_items_from_nmck_text(
        text, "nmck_services.docx"
    )


def test_xml_source_without_price_is_not_converted_to_economic_claim():
    text = "<root><purchaseObject><name>Кабель</name><quantity>3</quantity></purchaseObject></root>"
    assert (
        _invoke_direct(
            parsed.extract_supply_items_from_notification_xml, text, "notice.xml"
        )
        == []
    )
