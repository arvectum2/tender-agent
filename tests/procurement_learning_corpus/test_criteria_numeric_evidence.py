"""Explicit units can only be accepted from original-derived evidence."""
from src.tender_research.rag.numeric_claim_evidence import (
    unsupported_explicit_numeric_claim,
)
from src.tender_research.rag.search_types import RagSearchHit


def _source(text: str):
    return RagSearchHit(
        chunk_id="proof-source", registry_number="0163200000326005243",
        tender_id="official", tender_title="Электронный конкурс",
        customer_name="Дума", document_id="docsha",
        file_name="Подтверждённые веса критериев ЕИС (производный).docx",
        chunk_index=0, text=text, preview=text[:100], score=1.0,
    )


def test_verified_derived_percent_evidence_allows_exact_source_values():
    source=_source("Цена контракта 30%. Квалификация участников 70%. "
                   "Цена исполненных договоров 80%. Количество 20%.")
    assert unsupported_explicit_numeric_claim(
        "Цена 30%, квалификация 70%, показатели 80%/20%.", [source]
    ) is None


def test_percent_without_units_in_source_remains_blocked():
    raw_table=_source("Значимость критерия оценки, процентов: Цена контракта | 30; "
                      "Квалификация | 70")
    assert unsupported_explicit_numeric_claim(
        "Цена 30%, квалификация 70%.", [raw_table]
    ) == "percent"


def test_unrelated_or_invented_percent_rejected_even_if_others_verified():
    derived=_source("Цена 30%. Квалификация 70%.")
    assert unsupported_explicit_numeric_claim(
        "Квалификация 90%", [derived]
    ) == "percent"
