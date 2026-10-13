"""Requirement projections are adapter evidence, not invented original EIS facts."""

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_requirement_rows import (
    extract_requirement_rows,
    normalize_requirement_title,
)


def test_old_facade_and_service_specific_title():
    assert legacy._normalize_requirement_title(
        "Equipment/goods must match stated specifications", "services"
    ) == "Услуги должны быть оказаны в полном объеме и в соответствии с техническим заданием."
    assert legacy._normalize_requirement_title(
        "Equipment/goods must match stated specifications", "goods"
    ) == "Оборудование и товары должны соответствовать заявленной спецификации."


def test_translator_is_explicit_and_never_fabricates_missing_rows():
    seen = []
    def translate(value):
        seen.append(value)
        return f"РУ: {value}" if value else ""
    rows = extract_requirement_rows(
        {"technical_requirements": ["ТЗ", "", "Поставка"], "document_requirements": ["Справка"]},
        False,
        "goods",
        translate=translate,
    )
    assert len(rows) == 3
    assert all(row["source"] == "fallback-адаптер" for row in rows)
    assert all("адаптером" in row["detail"] or "Требование" in row["detail"] for row in rows)
    assert seen == ["ТЗ", "", "Поставка", "Справка"]


def test_complete_adapter_attribution_and_capped_rows():
    rows = legacy._extract_requirement_rows(
        {"technical_requirements": ["Позиция"] * 15, "document_requirements": ["Документ"]},
        True,
        "goods",
    )
    assert len(rows) == 10
    assert all(row["source"] == "адаптер раннера" for row in rows)


def test_empty_input_produces_no_requirements():
    assert legacy._extract_requirement_rows({}, False, "services") == []
    assert normalize_requirement_title("ТЗ", "goods", translate=lambda s: s) == "ТЗ"
