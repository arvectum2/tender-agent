"""Real DP processed document object may justify literal quote, not model claim."""

from __future__ import annotations

import hashlib

from src.modules.tender_operator_agent_demo.live_source_quote_bridge import (
    bind_quote_to_live_processed_document,
)
from src.shared.document_processing import ProcessedChunk, ProcessedDocument

QUOTE = "Срок оплаты составляет семь рабочих дней"


def _make_processed(*, text=QUOTE, hashed=True, resource_id="DP-R", document_id="DP-D"):
    return ProcessedDocument(
        extraction_status="extracted",
        text="  " + text.replace(" ", "   ") + "  ",
        chunks=(ProcessedChunk(
            index=0,
            text=text,
            text_hash=hashlib.sha256(text.encode()).hexdigest() if hashed else "fake",
            char_start=0,
            char_end=len(text),
            token_estimate=10,
            chunk_id="DP-CHUNK",
        ),),
        resource_id=resource_id,
        document_id=document_id,
        canonical_uri="tender-upload://sha256",
    )


def test_quoted_text_matches_real_dp_chunk_not_original_whitespace():
    original = _make_processed()
    assert QUOTE not in original.text
    evidence = bind_quote_to_live_processed_document(
        processed=original, file_id="FILE-03", exact_quote=QUOTE
    )
    assert evidence is not None
    assert evidence["file_id"] == "FILE-03"
    assert evidence["document_id"] == "DP-D"
    assert evidence["chunk_id"] == "DP-CHUNK"
    assert evidence["status"] == "literal_quote_found_in_hashed_dp_chunk_only"
    assert "pdf_page" not in evidence


def test_no_fabricated_evidence_for_paraphrases_hashes_or_identity():
    for source, quote in (
        (_make_processed(), "Оплата в течение недели"),
        (_make_processed(hashed=False), QUOTE),
        (_make_processed(document_id=None), QUOTE),
        (_make_processed(resource_id=None), QUOTE),
    ):
        assert bind_quote_to_live_processed_document(
            processed=source, file_id="FILE-03", exact_quote=quote,
        ) is None


def test_duplicate_chunk_identity_fails_closed():
    source = _make_processed()
    duplicate = ProcessedDocument(
        extraction_status=source.extraction_status,
        text=source.text,
        chunks=source.chunks + source.chunks,
        resource_id=source.resource_id,
        document_id=source.document_id,
        canonical_uri=source.canonical_uri,
    )
    assert bind_quote_to_live_processed_document(
        processed=duplicate, file_id="FILE-03", exact_quote=QUOTE,
    ) is None
