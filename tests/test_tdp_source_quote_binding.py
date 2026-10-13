"""Quote binding must use real hashed DP chunk content, not raw source offsets."""

from __future__ import annotations

import hashlib

import pytest

from src.modules.tender_operator_agent_demo.source_quote_binding import (
    bind_literal_source_quote,
)

RAW = "  Установлен  срок   оплаты в течение семи рабочих дней после приемки.  "
NORMALIZED_CHUNK = "Установлен срок оплаты в течение семи рабочих дней после приемки."
QUOTE = "Установлен срок оплаты в течение семи рабочих дней"
RECORD = {
    "resource_id": "DP-R001",
    "document_id": "DP-D001",
    "offset_space": "data_platform_normalized_text",
}
CHUNKS = [{
    "file_id": "FILE-03",
    "resource_id": "DP-R001",
    "document_id": "DP-D001",
    "chunk_id": "DP-CHUNK-001",
    "text_hash": hashlib.sha256(NORMALIZED_CHUNK.encode()).hexdigest(),
    "char_start": 0,
    "char_end": len(NORMALIZED_CHUNK),
}]
TEXTS = {"DP-CHUNK-001": NORMALIZED_CHUNK}


def bind(quote=QUOTE, chunks=None, texts=None, record=None):
    return bind_literal_source_quote(
        exact_quote=quote,
        file_id="FILE-03",
        source_record=RECORD if record is None else record,
        chunks=CHUNKS if chunks is None else chunks,
        chunk_text_by_id=TEXTS if texts is None else texts,
    )


def test_true_quote_binds_inside_hashed_normalized_chunk():
    assert QUOTE not in RAW  # Raw extracted text has different whitespace.
    evidence = bind()
    assert evidence is not None
    assert evidence["chunk_id"] == "DP-CHUNK-001"
    assert evidence["status"] == "literal_quote_found_in_hashed_dp_chunk_only"
    assert evidence["offset_space"] == "data_platform_chunk_text"
    assert NORMALIZED_CHUNK[
        evidence["quote_char_start_in_chunk"]:evidence["quote_char_end_in_chunk"]
    ] == QUOTE
    assert "char_start" not in evidence  # Never claim original DOCX offsets.


@pytest.mark.parametrize("quote", [
    "Срок оплаты семь рабочих дней",
    "В договоре штраф в размере десяти процентов.",
    "оплата",
    " " + QUOTE + " ",
])
def test_paraphrase_fake_short_or_trimmed_quote_fails(quote):
    assert bind(quote=quote) is None


def test_missing_or_inconsistent_chunk_identity_fails():
    for chunks in [
        [],
        [{**CHUNKS[0], "chunk_id": ""}],
        [{**CHUNKS[0], "document_id": "wrong"}],
        [{**CHUNKS[0], "text_hash": "forged"}],
        [{**CHUNKS[0], "char_end": 10}],
    ]:
        assert bind(chunks=chunks) is None


def test_without_actual_chunk_text_or_with_altered_text_fails():
    assert bind(texts={}) is None
    assert bind(texts={"DP-CHUNK-001": NORMALIZED_CHUNK+" FALSIFIED"}) is None


def test_duplicate_matching_chunks_are_ambiguous():
    assert bind(
        chunks=[CHUNKS[0], {**CHUNKS[0], "chunk_id": "DP-CHUNK-002"}],
        texts={**TEXTS, "DP-CHUNK-002": NORMALIZED_CHUNK},
    ) is None


def test_old_wrong_raw_offset_contract_is_rejected():
    assert bind(record={**RECORD, "offset_space": "data_platform_extracted_text_untrimmed"}) is None


def test_identical_quote_twice_inside_one_chunk_is_ambiguous():
    repeated = QUOTE + ". " + QUOTE + "."
    chunks = [{
        **CHUNKS[0],
        "char_end": len(repeated),
        "text_hash": hashlib.sha256(repeated.encode()).hexdigest(),
    }]
    assert bind(chunks=chunks, texts={"DP-CHUNK-001": repeated}) is None
