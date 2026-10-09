from src.tender_research.rag.numeric_absence_guard import contradicted_absence
from src.tender_research.rag.search_types import RagSearchHit


def _hit(text):
    return RagSearchHit(
        chunk_id="source-44-140",
        score=0.9,
        registry_number="0388100001826000047",
        tender_id="t",
        tender_title="Original EIS",
        customer_name=None,
        document_id="d",
        file_name="Описание объекта закупки.xlsx",
        chunk_index=0,
        preview=text[:50],
        text=text,
    )


def test_original_44_fz_140_tonnes_fails_false_absence():
    source = _hit(
        "Характеристики\t140\tТонна; метрическая тонна (1000 кг)\tТип топлива Зимнее"
    )
    assert (
        contradicted_absence(
            "Объем товара не указан в предоставленных данных.", [source]
        )
        == "quantity"
    )


def test_quantity_present_no_denial_is_not_rejected():
    assert contradicted_absence("Объём товара 140 тонн.", [_hit("140 тонн")]) is None


def test_absent_quantity_without_quantity_source_is_not_rejected():
    assert (
        contradicted_absence("Количество не указано.", [_hit("цена 140 рублей")])
        is None
    )


def test_223_fz_explicit_percent_missing_is_contradicted_by_document():
    assert (
        contradicted_absence(
            "Значимость критерия не указана.",
            [_hit("Стоимостной критерий 40%, нестоимостной 60%")],
        )
        == "percent"
    )


def test_numeric_but_unrelated_context_is_not_confused():
    assert (
        contradicted_absence("Цена не указана.", [_hit("Поставка в срок 31.12.2027")])
        is None
    )


def test_no_numeric_denial_ignores_other_values():
    assert contradicted_absence("Срок 31.12.2027.", [_hit("31.12.2027")]) is None
