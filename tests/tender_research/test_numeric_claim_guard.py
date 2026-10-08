from src.tender_research.rag.numeric_claim_guard import contradicted_cited_quantity
from src.tender_research.rag.search_types import RagSearchHit


def _hit(text, chunk_id="doc-44-chunk"):
    return RagSearchHit(
        chunk_id=chunk_id,
        score=0.9,
        registry_number="0388100001826000047",
        tender_id="t",
        tender_title="Закупка",
        customer_name=None,
        document_id="doc",
        file_name="Описание объекта закупки.xlsx",
        chunk_index=0,
        preview=text[:40],
        text=text,
    )


def test_wrong_tonnes_against_same_cited_source():
    assert (
        contradicted_cited_quantity(
            "Объём: 150 тонн, chunk_id=doc-44-chunk", [_hit("Количество 140 тонн.")]
        )
        == "quantity"
    )


def test_exact_amount_accepted():
    assert (
        contradicted_cited_quantity(
            "Объём: 140 тонн, chunk_id=doc-44-chunk", [_hit("Количество 140 тонн.")]
        )
        is None
    )


def test_ambiguous_source_amounts_are_unknown():
    assert (
        contradicted_cited_quantity(
            "Объём: 150 тонн, chunk_id=doc-44-chunk",
            [_hit("Лот 1: 140 тонн, лот 2: 150 тонн")],
        )
        is None
    )


def test_unrelated_uncited_number_is_not_checked():
    assert contradicted_cited_quantity("Ожидаем 150 тонн.", [_hit("140 тонн")]) is None


def test_wrong_other_chunk_reference_is_not_mapped():
    assert (
        contradicted_cited_quantity(
            "150 тонн, chunk_id=some-other-id", [_hit("140 тонн")]
        )
        is None
    )


def test_other_unit_not_conflated():
    assert (
        contradicted_cited_quantity("150 кг, chunk_id=doc-44-chunk", [_hit("140 тонн")])
        is None
    )


def test_different_lines_are_not_fused():
    assert (
        contradicted_cited_quantity(
            "150 тонн\nchunk_id=doc-44-chunk", [_hit("140 тонн")]
        )
        is None
    )


def test_shared_llm_completion_gate_rejects_wrong_cited_quantity():
    from src.tender_research.rag.llm import _validate_source_bound_completion

    answer = "Объём 150 тонн, chunk_id=doc-44-chunk"
    error = _validate_source_bound_completion(
        {"choices": [{"finish_reason": "stop"}]},
        answer,
        [_hit("ГСМ: 140 тонн. Топливо дизельное зимнее.")],
    )
    assert "numeric claim conflicts" in error


def test_shared_llm_completion_gate_accepts_exact_cited_quantity():
    from src.tender_research.rag.llm import _validate_source_bound_completion

    assert (
        _validate_source_bound_completion(
            {"choices": [{"finish_reason": "stop"}]},
            "Объём 140 тонн, chunk_id=doc-44-chunk",
            [_hit("ГСМ: 140 тонн.")],
        )
        is None
    )
