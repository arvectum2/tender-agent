from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RagSearchHit:
    """Backend-neutral retrieval result consumed by Tender Agent domain logic."""

    chunk_id: str
    score: float
    registry_number: str | None
    tender_id: str
    tender_title: str
    customer_name: str | None
    document_id: str
    file_name: str
    chunk_index: int
    preview: str
    text: str
