"""Conservative literal quote binding against an actual DP chunk.

DP chunk offsets refer to platform-NORMALIZED text, not raw extracted text;
a chunk may also strip boundary whitespace. Bind quotations to the exact
chunk text returned by DP and its SHA256, NEVER reconstruct raw PDF/DOC
coordinates from global normalized offsets. The binder does NOT verify a
model's legal interpretation or promote an unsourced claim.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any


def bind_literal_source_quote(
    *,
    exact_quote: str,
    file_id: str,
    source_record: dict[str, Any],
    chunks: list[dict[str, Any]],
    chunk_text_by_id: Mapping[str, str],
    min_chars: int = 20,
) -> dict[str, Any] | None:
    if (
        not isinstance(exact_quote, str)
        or len(exact_quote.strip()) < min_chars
        or exact_quote != exact_quote.strip()
        or not isinstance(file_id, str)
        or not file_id.strip()
    ):
        return None
    resource_id = source_record.get("resource_id")
    document_id = source_record.get("document_id")
    if (
        source_record.get("offset_space") != "data_platform_normalized_text"
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
        chunk_id = chunk.get("chunk_id")
        if (
            chunk.get("file_id") != file_id
            or chunk.get("resource_id") != resource_id
            or chunk.get("document_id") != document_id
            or not isinstance(chunk_id, str)
            or not chunk_id.strip()
        ):
            continue
        text = chunk_text_by_id.get(chunk_id)
        if not isinstance(text, str) or not text:
            continue
        expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if chunk.get("text_hash") != expected_hash:
            continue
        start, end = chunk.get("char_start"), chunk.get("char_end")
        if (
            type(start) is not int
            or type(end) is not int
            or start < 0
            or end < start
            or end - start < len(text)
            or text.count(exact_quote) != 1
        ):
            continue
        location = text.find(exact_quote)
        matches.append({
            "file_id": file_id,
            "resource_id": resource_id,
            "document_id": document_id,
            "chunk_id": chunk_id,
            "quote": exact_quote,
            "quote_char_start_in_chunk": location,
            "quote_char_end_in_chunk": location + len(exact_quote),
            "offset_space": "data_platform_chunk_text",
            "status": "literal_quote_found_in_hashed_dp_chunk_only",
        })
    # Ambiguous source matches must not be attributed to a single chunk.
    return matches[0] if len(matches) == 1 else None
