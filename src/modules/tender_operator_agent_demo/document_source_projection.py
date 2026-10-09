"""Source-identity projection from Data Platform to Tender Agent file records.

Stores no extracted raw content and never invents OCR/PDF page numbers. Chunk
offsets are in UNTRIMMED Data Platform extracted-text coordinate space; the
separate normalized text saved by the legacy operator may trim whitespace.
"""

from __future__ import annotations

from typing import Any

from src.shared.document_processing import ProcessedDocument


def project_document_source(
    processed: ProcessedDocument,
    *,
    file_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    original = processed.text
    leading_trim = len(original) - len(original.lstrip())
    trailing_trim = len(original) - len(original.rstrip())
    chunks: list[dict[str, Any]] = []
    for chunk in processed.chunks:
        if (
            not chunk.chunk_id
            or not processed.document_id
            or not processed.resource_id
            or chunk.char_start < 0
            or chunk.char_end < chunk.char_start
            or chunk.char_end > len(original)
        ):
            continue
        chunks.append({
            "file_id": file_id,
            "resource_id": processed.resource_id,
            "document_id": processed.document_id,
            "chunk_id": chunk.chunk_id,
            "text_hash": chunk.text_hash,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
            "token_estimate": chunk.token_estimate,
        })

    provenance = {
        "contract": "arvectum-data-consumer-v1",
        "resource_id": processed.resource_id,
        "document_id": processed.document_id,
        "canonical_uri": processed.canonical_uri,
        "extraction_status": processed.extraction_status,
        "source_chunk_count": len(processed.chunks),
        "attributable_chunk_count": len(chunks),
        "offset_space": "data_platform_extracted_text_untrimmed",
        "normalized_text_leading_trim_chars": leading_trim,
        "normalized_text_trailing_trim_chars": trailing_trim,
    }
    return provenance, chunks
