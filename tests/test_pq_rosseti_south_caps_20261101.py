"""Small regression for the source-guarded Rosseti South field enrichment."""
import pytest

from scripts.market_intelligence.enrich_pq_rosseti_south_caps_20261101 import (
    FIELDS,
    check_itemized_quantity,
    check_protocol_text,
)


def test_scope_and_price_separation():
    assert FIELDS["quantity"] == 24
    assert FIELDS["contract_registered_price_rub"] == "4350000.00"
    assert "supplier_inn" not in FIELDS
    assert "pq_equipment_only_contract_rub" not in FIELDS
    assert "paid_verified" not in FIELDS


def test_protocol_requires_exact_primary_quotes():
    text = (
        "Итоговый протокол №32616339168-01 от 10.09.2026 "
        "Начальная цена 6 807 600.00. Заявка 2: 4 350 000.00. "
        "Заявка 1: 5 122 536.00. Результат: 1 место. Заключение договора"
    )
    check_protocol_text(text)
    with pytest.raises(ValueError, match="Protocol original missing quote"):
        check_protocol_text(text.replace("4 350 000.00", "4 351 000.00"))


def test_quantity_requires_all_six_item_rows():
    text = " ".join(f"Конденсатор {q}, Штука 123 456.00" for q in (11, 1, 5, 1, 5, 1))
    check_itemized_quantity(text)
    with pytest.raises(ValueError, match="quantity"):
        check_itemized_quantity(text.replace("11, Штука", "10, Штука"))
