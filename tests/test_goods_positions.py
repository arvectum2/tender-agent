from types import SimpleNamespace

from src.modules.tender_operator_agent_demo.goods_source_facts import (
    build_goods_positions_from_source_items,
)


def _item(position: int, name: str, quantity: str, *, source: str = "NMCK.docx") -> SimpleNamespace:
    return SimpleNamespace(
        item_type="goods",
        source_kind="nmck_xlsx",
        item_no=str(position),
        name=name,
        quantity=quantity,
        unit="м",
        unit_original="м",
        okpd2="27.32.13.111",
        ktru=None,
        source_document=source,
        source_row_number=position + 10,
        evidence_id=f"ev-{position}",
    )


def test_goods_positions_preserve_duplicate_names_and_row_provenance():
    positions, provenance = build_goods_positions_from_source_items(
        [_item(1, "Кабель КГтп-ХЛ", "30"), _item(2, "Кабель КГтп-ХЛ", "50")]
    )

    assert positions == [
        {"name": "Кабель КГтп-ХЛ", "okpd2_ktru": "27.32.13.111", "position": 1, "quantity": 30, "unit": "м"},
        {"name": "Кабель КГтп-ХЛ", "okpd2_ktru": "27.32.13.111", "position": 2, "quantity": 50, "unit": "м"},
    ]
    assert provenance == [
        {"position": "1", "source_document": "NMCK.docx", "locator": "row:11", "evidence_id": "ev-1"},
        {"position": "2", "source_document": "NMCK.docx", "locator": "row:12", "evidence_id": "ev-2"},
    ]


def test_goods_positions_fail_closed_for_competing_or_gapped_tables():
    assert build_goods_positions_from_source_items([_item(1, "A", "1"), _item(3, "B", "2")]) == ([], [])
    assert build_goods_positions_from_source_items(
        [_item(1, "A", "1"), _item(1, "B", "2", source="other.docx")]
    ) == ([], [])
