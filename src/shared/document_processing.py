from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass, field
from typing import Any

from src.shared.config.settings import Settings, get_settings
from src.shared.data_platform import DataPlatformHttpClient

EXTRACTED_STATUS = "extracted"
FAILED_STATUS = "failed"
UNSUPPORTED_STATUS = "unsupported"
EMPTY_STATUS = "empty"


@dataclass(frozen=True)
class ProcessedChunk:
    index: int
    text: str
    text_hash: str
    char_start: int
    char_end: int
    token_estimate: int
    chunk_id: str | None = None


@dataclass(frozen=True)
class ProcessedDocument:
    extraction_status: str
    text: str
    chunks: tuple[ProcessedChunk, ...]
    # Preserves canonical generic provenance returned by the Data Platform SDK.
    # All fields remain optional for existing deterministic/unit adapters.
    resource_id: str | None = None
    document_id: str | None = None
    canonical_uri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def process_document_bytes(
    *,
    content: bytes,
    filename: str,
    collection_id: str,
    canonical_uri: str | None = None,
    content_type: str | None = None,
    max_chars: int | None = None,
    chunk_size_chars: int | None = None,
    overlap_chars: int | None = None,
    min_chunk_chars: int | None = None,
    settings: Settings | None = None,
    client: DataPlatformHttpClient | None = None,
) -> ProcessedDocument:
    runtime = settings or get_settings()
    if chunk_size_chars is not None and chunk_size_chars <= 0:
        raise ValueError("chunk_size_chars must be positive")
    resolved_overlap = (
        runtime.rag_chunk_overlap_chars if overlap_chars is None else overlap_chars
    )
    resolved_chunk_size = (
        runtime.rag_chunk_size_chars if chunk_size_chars is None else chunk_size_chars
    )
    if resolved_overlap < 0 or resolved_overlap >= resolved_chunk_size:
        raise ValueError("overlap_chars must be non-negative and smaller than chunk_size_chars")

    digest = hashlib.sha256(content).hexdigest()
    uri = canonical_uri or f"content-sha256://{digest}"
    mime = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    kwargs = {
        "collection_id": collection_id,
        "canonical_uri": uri,
        "title": filename,
        "content": content,
        "filename": filename,
        "content_type": mime,
        "chunk_size_chars": resolved_chunk_size,
        "overlap_chars": resolved_overlap,
        "min_chunk_chars": (
            runtime.rag_min_chunk_chars
            if min_chunk_chars is None
            else min_chunk_chars
        ),
        "max_chars": (
            runtime.document_extract_max_chars if max_chars is None else max_chars
        ),
    }

    owns_client = client is None
    platform = client or DataPlatformHttpClient(
        base_url=runtime.rag_data_platform_base_url,
        api_key=runtime.rag_data_platform_api_key,
        timeout_seconds=runtime.rag_data_platform_timeout_seconds,
    )
    try:
        payload = platform.process_document(**kwargs)
    finally:
        if owns_client:
            platform.close()

    status = str(payload.get("extraction_status") or FAILED_STATUS)
    text = str(payload.get("text") or "")
    raw_chunks = payload.get("chunks")
    if not isinstance(raw_chunks, list):
        raw_chunks = []
    chunks: list[ProcessedChunk] = []
    for item in raw_chunks:
        if not isinstance(item, dict):
            continue
        chunks.append(
            ProcessedChunk(
                index=int(item.get("ordinal", len(chunks))),
                text=str(item.get("text") or ""),
                text_hash=str(item.get("content_hash") or ""),
                char_start=int(item.get("char_start", 0)),
                char_end=int(item.get("char_end", 0)),
                token_estimate=int(item.get("token_estimate", 0)),
                chunk_id=str(item["chunk_id"]) if item.get("chunk_id") else None,
            )
        )
    return ProcessedDocument(
        extraction_status=status,
        text=text,
        chunks=tuple(chunks),
        resource_id=str(payload["resource_id"]) if payload.get("resource_id") else None,
        document_id=str(payload["document_id"]) if payload.get("document_id") else None,
        canonical_uri=str(payload.get("canonical_uri") or uri),
        metadata=dict(payload["metadata"]) if isinstance(payload.get("metadata"), dict) else {},
    )
