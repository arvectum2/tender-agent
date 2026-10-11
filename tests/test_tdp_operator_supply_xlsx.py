"""Candidate XLSX extraction is a bounded module behind the legacy facade."""

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_supply_xlsx import (
    extract_supply_items_from_xlsx_text,
)


def _direct(text: str):
    return extract_supply_items_from_xlsx_text(
        text,
        "nmck-test.xlsx",
        supply_item_type=legacy.SupplyItem,
        supply_unit_pattern=legacy._SUPPLY_UNIT_PATTERN,
        _cleanup_tabular_value=legacy._cleanup_tabular_value,
        _is_line_item_name=legacy._is_line_item_name,
        _parse_float=legacy._parse_float,
        _is_ktru_or_okpd=legacy._is_ktru_or_okpd,
        _split_trailing_classification=legacy._split_trailing_classification,
        _normalize_quantity_value=legacy._normalize_quantity_value,
        _normalize_supply_name=legacy._normalize_supply_name,
        _normalize_supply_unit=legacy._normalize_supply_unit,
        _extract_gost_tokens=legacy._extract_gost_tokens,
        _format_decimal_price=legacy._format_decimal_price,
    )


def test_xlsx_module_direct_and_original_facade_preserve_same_source_provenance():
    source = (
        "№\tНаименование\tКТРУ\tЕд.\tКол-во\tИтого\n"
        "1\tПапка пластиковая\t27.32.13.111\tшт\t5\t150,00\n"
    )
    original = legacy._extract_supply_items_from_xlsx_text(source, "nmck-test.xlsx")
    extracted = _direct(source)
    assert extracted == original
    assert len(extracted) == 1
    assert type(extracted[0]) is legacy.SupplyItem
    assert extracted[0].source_kind == "nmck_xlsx"
    assert extracted[0].source_document == "nmck-test.xlsx"
    assert extracted[0].raw_fragment.startswith("1\tПапка")
    assert extracted[0].ktru == "27.32.13.111"
    assert extracted[0].evidence_id == original[0].evidence_id


def test_xlsx_ambiguous_quantity_is_not_invented_as_verified_good():
    source = "№\tНаименование\tЕд.\tКол-во\n1\tПапка\tшт\tНЕИЗВЕСТНО\n"
    assert _direct(source) == []
    assert legacy._extract_supply_items_from_xlsx_text(source, "nmck-test.xlsx") == []
