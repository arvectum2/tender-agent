"""Ephemeral DP document-to-quote bridge; never store source chunk plaintext."""

from __future__ import annotations

from src.modules.tender_operator_agent_demo.document_source_projection import (
    project_document_source,
)
from src.modules.tender_operator_agent_demo.source_quote_binding import (
    bind_literal_source_quote,
)
from src.shared.document_processing import ProcessedDocument


def bind_quote_to_live_processed_document(
    *,
    processed: ProcessedDocument,
    file_id: str,
    exact_quote: str,
) -> dict[str, object] | None:
    """Verify a literal quote against genuine in-memory DP chunk payloads.

    A match proves only occurrence in a hashed extracted chunk, not that the
    model's assertion, amount, deadline, or legal interpretation is correct.
    Fail closed on duplicate chunk IDs and missing/ambiguous DP provenance.
    """
    provenance, candidates = project_document_source(processed, file_id=file_id)
    indexed: dict[str, str] = {}
    duplicate_ids: set[str] = set()
    for chunk in processed.chunks:
        if not chunk.chunk_id:
            continue
        if chunk.chunk_id in indexed:
            duplicate_ids.add(chunk.chunk_id)
        else:
            indexed[chunk.chunk_id] = chunk.text
    for chunk_id in duplicate_ids:
        indexed.pop(chunk_id, None)
    return bind_literal_source_quote(
        exact_quote=exact_quote,
        file_id=file_id,
        source_record=provenance,
        chunks=[record for record in candidates if record["chunk_id"] not in duplicate_ids],
        chunk_text_by_id=indexed,
    )
