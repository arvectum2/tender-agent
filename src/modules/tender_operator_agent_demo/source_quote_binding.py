"""Fail-closed binding of an explicit literal quote to a DP source chunk.

The binder proves only text occurrence in an extracted, identified source. It
does not prove the LLM conclusion, legal interpretation, PDF page or OCR truth.
No fuzzy model sentence matching or fabricated source IDs are allowed.
"""

from __future__ import annotations

from typing import Any


def bind_literal_source_quote(
    *,
    exact_quote: str,
    original_extracted_text: str,
    file_id: str,
    source_record: dict[str, Any],
    chunks: list[dict[str, Any]],
    min_chars: int = 20,
) -> dict[str, Any] | None:
    if (
        not isinstance(exact_quote, str)
        or len(exact_quote.strip()) < min_chars
        or exact_quote != exact_quote.strip()
        or not isinstance(original_extracted_text, str)
        or not isinstance(file_id, str)
        or not file_id.strip()
    ):
        return None
    resource_id = source_record.get("resource_id")
    document_id = source_record.get("document_id")
    if (
        source_record.get("offset_space") != "data_platform_extracted_text_untrimmed"
        or not isinstance(resource_id, str)
        or not resource_id.strip()
        or not isinstance(document_id, str)
        or not document_id.strip()
    ):
        return None

    matches: list[dict[str, Any]] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        if (
            chunk.get("file_id") != file_id
            or chunk.get("resource_id") != resource_id
            or chunk.get("document_id") != document_id
            or not isinstance(chunk.get("chunk_id"), str)
            or not chunk["chunk_id"].strip()
        ):
            continue
        start, end = chunk.get("char_start"), chunk.get("char_end")
        if (
            type(start) is not int
            or type(end) is not int
            or start < 0
            or end < start
            or end > len(original_extracted_text)
        ):
            continue
        location = original_extracted_text.find(exact_quote, start, end)
        if location == -1 or location + len(exact_quote) > end:
            continue
        matches.append({
            "file_id": file_id,
            "resource_id": resource_id,
            "document_id": document_id,
            "chunk_id": chunk["chunk_id"],
            "quote": exact_quote,
            "char_start": location,
            "char_end": location + len(exact_quote),
            "offset_space": "data_platform_extracted_text_untrimmed",
            "status": "literal_quote_found_in_extracted_text_only",
        })
    # Ambiguous matches cannot be reported as unique evidence.
    return matches[0] if len(matches) == 1 else None
