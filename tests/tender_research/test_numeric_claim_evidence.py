from src.tender_research.rag.numeric_claim_evidence import (
    unsupported_explicit_numeric_claim,
)
from src.tender_research.rag.search_types import RagSearchHit


def hit(text):
    return RagSearchHit(
        chunk_id="original",
        score=1,
        registry_number="0388100001826000047",
        tender_id="t",
        tender_title="Original",
        customer_name=None,
        document_id="d",
        file_name="Описание объекта закупки.xlsx",
        chunk_index=0,
        preview=text,
        text=text,
    )


def test_rejects_hallucinated_tonnes_150_when_source_140():
    assert (
        unsupported_explicit_numeric_claim(
            "Требуется 150 тонн дизеля.", [hit("140 Тонна; метрическая тонна")]
        )
        == "tonnes"
    )


def test_accepts_matching_source_quantity():
    assert (
        unsupported_explicit_numeric_claim(
            "Требуется 140 тонн.", [hit("140 Тонна; метрическая тонна")]
        )
        is None
    )


def test_rejects_fabricated_223_fz_criterion_percentage():
    assert (
        unsupported_explicit_numeric_claim(
            "Стоимость 45%.", [hit("Стоимостной критерий 40%, нестоимостной 60%")]
        )
        == "percent"
    )


def test_accepts_existing_223_fz_criterion_weights():
    assert (
        unsupported_explicit_numeric_claim("Критерии 40% и 60%.", [hit("40% / 60%")])
        is None
    )


def test_ignores_dates_and_registry_numbers_without_supported_units():
    assert (
        unsupported_explicit_numeric_claim(
            "Реестр 0388100001826000047, срок 2027.", [hit("ТЗ: 2027")]
        )
        is None
    )


def test_rejects_unsupported_ruble_sum():
    assert (
        unsupported_explicit_numeric_claim(
            "Цена 500 000 рублей.", [hit("Стоимость 400 000 руб.")]
        )
        == "rub"
    )
