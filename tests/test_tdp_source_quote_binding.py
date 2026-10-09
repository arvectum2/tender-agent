"""Exact source-quote linking cannot promote a plausible LLM claim to verified."""

from __future__ import annotations

import pytest

from src.modules.tender_operator_agent_demo.source_quote_binding import (
    bind_literal_source_quote,
)

TEXT = "  Установлен срок оплаты в течение семи рабочих дней после приемки. Штрафы определены условиями договора.  "
QUOTE = "Установлен срок оплаты в течение семи рабочих дней"
RECORD = {
    "resource_id": "DP-R001",
    "document_id": "DP-D001",
    "offset_space": "data_platform_extracted_text_untrimmed",
}
CHUNKS = [{
    "file_id": "FILE-03",
    "resource_id": "DP-R001",
    "document_id": "DP-D001",
    "chunk_id": "DP-CHUNK-001",
    "char_start": 0,
    "char_end": len(TEXT),
}]


def test_exact_quote_binds_once_to_real_dp_chunk_coordinates():
    evidence = bind_literal_source_quote(
        exact_quote=QUOTE,
        original_extracted_text=TEXT,
        file_id="FILE-03",
        source_record=RECORD,
        chunks=CHUNKS,
    )
    assert evidence is not None
    assert evidence["status"] == "literal_quote_found_in_extracted_text_only"
    assert evidence["chunk_id"] == "DP-CHUNK-001"
    assert TEXT[evidence["char_start"]:evidence["char_end"]] == QUOTE
    assert evidence["offset_space"] == "data_platform_extracted_text_untrimmed"
    assert "original_pdf_page" not in evidence


@pytest.mark.parametrize("quote", [
    "Срок оплаты семь рабочих дней",  # Semantic paraphrase is not source evidence
    "В договоре предусмотрен штраф в размере десяти процентов.",  # Model hallucination
    "оплата",  # Overly short/ambiguous
    " " + QUOTE + " ",
])
def test_unattributable_model_text_never_gets_source_id(quote):
    assert bind_literal_source_quote(
        exact_quote=quote, original_extracted_text=TEXT,
        file_id="FILE-03", source_record=RECORD, chunks=CHUNKS,
    ) is None


def test_missing_chunk_or_mismatched_original_is_not_promoted():
    for chunks in (
        [],
        [{**CHUNKS[0], "chunk_id": None}],
        [{**CHUNKS[0], "document_id": "wrong"}],
        [{**CHUNKS[0], "char_end": 12}],
        [{**CHUNKS[0], "char_end": 100000}],
    ):
        assert bind_literal_source_quote(
            exact_quote=QUOTE, original_extracted_text=TEXT,
            file_id="FILE-03", source_record=RECORD, chunks=chunks,
        ) is None


def test_duplicate_chunk_hits_are_ambiguous():
    assert bind_literal_source_quote(
        exact_quote=QUOTE, original_extracted_text=TEXT,
        file_id="FILE-03", source_record=RECORD,
        chunks=[CHUNKS[0], {**CHUNKS[0], "chunk_id": "DP-CHUNK-002"}],
    ) is None


def test_trimmed_coordinates_cannot_masquerade_as_platform_offsets():
    assert bind_literal_source_quote(
        exact_quote=QUOTE, original_extracted_text=TEXT.strip(),
        file_id="FILE-03",
        source_record={**RECORD, "offset_space": "normalized_trimmed_text"},
        chunks=CHUNKS,
    ) is None
