"""Structured tabular goods parsing beyond the legacy 24-row cap.

Synthetic fixtures only: no procurement numbers, no real tender documents.
"""

from src.modules.procurement_analysis.frozen_types import AnalyzedDocument
from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.goods_source_facts import (
    build_complete_goods_positions,
)


def _nmck_text(rows: list[tuple[str, str, str, str]]) -> str:
    lines = ["№ п/п\tПредмет закупки\tЕд. изм.\tКол-во\tЦена"]
    for item_no, name, unit, quantity in rows:
        lines.append(f"{item_no}\t{name}\t{unit}\t{quantity}\t100,00")
    return "\n".join(lines)


def _thirty_rows() -> list[tuple[str, str, str, str]]:
    units = ["шт", "м", "упак", "рул"]
    return [
        (str(i), f"Изделие {i}", units[i % 4], str(i * 10))
        for i in range(1, 31)
    ]


def test_thirty_row_nmck_table_returns_all_rows():
    items = legacy._extract_supply_items_from_xlsx_text(
        _nmck_text(_thirty_rows()), "nmck-synthetic.xlsx"
    )

    assert len(items) == 30
    assert [item.item_no for item in items] == [str(i) for i in range(1, 31)]
    assert [item.source_row_number for item in items] == list(range(1, 31))


def test_source_order_and_quantities_preserved():
    items = legacy._extract_supply_items_from_xlsx_text(
        _nmck_text(_thirty_rows()), "nmck-synthetic.xlsx"
    )

    assert items[0].quantity == "10"
    assert items[29].quantity == "300"
    assert items[0].unit == "м"
    assert items[1].unit == "упак"
    assert items[2].unit == "рул"


def test_duplicate_looking_names_remain_distinct_rows():
    rows = [
        ("1", "Папка пластиковая", "шт", "600"),
        ("2", "Папка пластиковая", "шт", "500"),
        ("3", "Папка пластиковая", "шт", "100"),
    ]
    items = legacy._extract_supply_items_from_xlsx_text(
        _nmck_text(rows), "nmck-synthetic.xlsx"
    )

    assert len(items) == 3
    assert {item.item_no for item in items} == {"1", "2", "3"}


def test_ktru_trailing_suffix_split_from_name():
    items = legacy._extract_supply_items_from_xlsx_text(
        _nmck_text([("1", "Папка пластиковая КТРУ 22.29.25.000-00000010", "шт", "600")]),
        "nmck-synthetic.xlsx",
    )

    assert len(items) == 1
    assert items[0].name == "Папка пластиковая"
    assert items[0].ktru == "22.29.25.000-00000010"
    assert items[0].okpd2 is None


def test_ktru_dash_variant_split_from_name():
    items = legacy._extract_supply_items_from_xlsx_text(
        _nmck_text([("1", "Подушка КТРУ-22.29.25.000-00000030", "шт", "10")]),
        "nmck-synthetic.xlsx",
    )

    assert items[0].name == "Подушка"
    assert items[0].ktru == "22.29.25.000-00000030"


def test_okpd2_trailing_suffix_stored_in_okpd2():
    items = legacy._extract_supply_items_from_xlsx_text(
        _nmck_text([("1", "Папка адресная ОКПД 2-17.23.13.193", "шт", "200")]),
        "nmck-synthetic.xlsx",
    )

    assert items[0].name == "Папка адресная"
    assert items[0].ktru is None
    assert items[0].okpd2 == "17.23.13.193"


def test_dedicated_identifier_column_takes_precedence():
    text = (
        "№\tНаименование\tКТРУ\tЕд.\tКол-во\n"
        "1\tПапка КТРУ 22.29.25.000-00000010\t27.32.13.111\tшт\t5"
    )
    items = legacy._extract_supply_items_from_xlsx_text(text, "nmck-synthetic.xlsx")

    assert len(items) == 1
    assert items[0].ktru == "27.32.13.111"


def test_unlabeled_numeric_suffix_is_not_classification():
    items = legacy._extract_supply_items_from_xlsx_text(
        _nmck_text([("1", "Папка 22.29.25.000-00000010", "шт", "5")]),
        "nmck-synthetic.xlsx",
    )

    assert items[0].ktru is None
    assert items[0].okpd2 is None
    assert "22.29.25.000-00000010" in items[0].name


def test_product_name_containing_list_substring_is_not_a_sheet_header():
    items = legacy._extract_supply_items_from_xlsx_text(
        _nmck_text([("28", "Разделитель листов пластиковый КТРУ-22.29.25.000-00000034", "упак", "10")]),
        "nmck-synthetic.xlsx",
    )

    assert len(items) == 1
    assert items[0].name == "Разделитель листов пластиковый"
    assert items[0].ktru == "22.29.25.000-00000034"


def test_standalone_sheet_marker_rows_are_still_skipped():
    items = legacy._extract_supply_items_from_xlsx_text(
        "лист 1\tSheet\tшт\t5\n"
        + _nmck_text([("1", "Изделие 1", "шт", "10")]).split("\n", 1)[1],
        "nmck-synthetic.xlsx",
    )

    assert [item.item_no for item in items] == ["1"]


def test_raw_fragment_retains_original_line():
    line = "1\tПапка пластиковая КТРУ 22.29.25.000-00000010\tшт\t600\t100,00"
    items = legacy._extract_supply_items_from_xlsx_text(
        "№ п/п\tПредмет закупки\tЕд. изм.\tКол-во\tЦена\n" + line,
        "nmck-synthetic.xlsx",
    )

    assert items[0].raw_fragment == line


def _document(rows: list) -> AnalyzedDocument:
    return AnalyzedDocument(
        display_name="nmck-synthetic.xlsx",
        extension=".xlsx",
        role="other",
        text=_nmck_text(rows),
        extracted_text_available=True,
        warnings=[],
        source="test",
        file_id="FILE-TEST",
    )


def test_complete_structured_rows_produce_canonical_positions():
    positions = build_complete_goods_positions(
        legacy._collect_unmerged_source_items([_document(_thirty_rows())])
    )

    assert len(positions) == 30
    assert [row["source_row_number"] for row in positions] == list(range(1, 31))
    assert all(row["evidence_id"] for row in positions)
    assert all(row["source_document"] == "nmck-synthetic.xlsx" for row in positions)


def test_incomplete_or_competing_tables_still_fail_closed():
    single = legacy._collect_unmerged_source_items(
        [_document([("1", "Изделие 1", "шт", "10")])]
    )
    assert build_complete_goods_positions(single) == []

    other = AnalyzedDocument(
        display_name="other-nmck.xlsx",
        extension=".xlsx",
        role="other",
        text=_nmck_text([("1", "Изделие 1", "шт", "10"), ("2", "Изделие 2", "шт", "5")]),
        extracted_text_available=True,
        warnings=[],
        source="test",
        file_id="FILE-OTHER",
    )
    competing = legacy._collect_unmerged_source_items(
        [_document(_thirty_rows()[:2]), other]
    )
    assert build_complete_goods_positions(competing) == []
