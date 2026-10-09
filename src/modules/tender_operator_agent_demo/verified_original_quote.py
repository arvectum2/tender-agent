"""Read-only original-document attestation for an explicitly supplied literal quote.

Re-extracts an authorized saved original through Data Platform's non-persisting
process endpoint, then checks stable IDs, chunk SHA256 and the exact quote.
A matched excerpt does not prove a legal interpretation.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.modules.tender_operator_agent_demo.source_quote_binding import (
    bind_literal_source_quote,
)
from src.shared.data_platform import DataPlatformError
from src.shared.document_processing import ProcessedDocument

MAX_VERIFIABLE_ORIGINAL_BYTES = 12 * 1024 * 1024


def attest_original_quote(
    *,
    input_root: Path,
    file_record: dict[str, Any],
    exact_quote: str,
    collection_id: str,
    processor: Callable[..., ProcessedDocument],
    max_original_bytes: int = MAX_VERIFIABLE_ORIGINAL_BYTES,
) -> dict[str, Any] | None:
    """Verify a literal quote against a saved original; no writes or logging.

    Call only after user and run authorization. The processor must be the
    non-persisting Data Platform process consumer, never the ingest consumer.
    """
    stored_name = file_record.get("stored_name")
    file_id = file_record.get("file_id")
    provenance = file_record.get("data_platform_source")
    saved_chunks = file_record.get("evidence_chunks")
    if (
        not isinstance(stored_name, str)
        or not stored_name
        or Path(stored_name).name != stored_name
        or "/" in stored_name or "\\" in stored_name
        or stored_name in {".", ".."}
        or not isinstance(file_id, str)
        or not file_id
        or not isinstance(provenance, dict)
        or not isinstance(saved_chunks, list)
        or not saved_chunks
        or not isinstance(collection_id, str)
        or not collection_id
        or type(max_original_bytes) is not int
        or max_original_bytes <= 0
    ):
        return None

    try:
        root = input_root.resolve(strict=True)
        candidate = root / stored_name
        if candidate.is_symlink():
            return None
        source = candidate.resolve(strict=True)
        if source.parent != root or not source.is_file():
            return None
        size = source.stat().st_size
        if size <= 0 or size > max_original_bytes:
            return None
        content = source.read_bytes()
        if len(content) != size:
            return None
        uri = "tender-upload://" + hashlib.sha256(content).hexdigest()
        if uri != provenance.get("canonical_uri"):
            return None

        processed = processor(
            content=content,
            filename=stored_name,
            collection_id=collection_id,
            canonical_uri=uri,
            min_chunk_chars=1,
        )
    except (DataPlatformError, ValueError, OSError):
        return None

    if (
        not isinstance(processed, ProcessedDocument)
        or processed.canonical_uri != uri
        or processed.resource_id != provenance.get("resource_id")
        or processed.document_id != provenance.get("document_id")
        or processed.extraction_status != provenance.get("extraction_status")
    ):
        return None

    chunk_texts = {c.chunk_id: c.text for c in processed.chunks if c.chunk_id}
    result = bind_literal_source_quote(
        exact_quote=exact_quote,
        file_id=file_id,
        source_record=provenance,
        chunks=saved_chunks,
        chunk_text_by_id=chunk_texts,
    )
    if result is None:
        return None
    return {**result, "original_sha256": hashlib.sha256(content).hexdigest()}


def verify_operator_run_quote(
    *, run_id: str, file_id: str, exact_quote: str,
) -> dict[str, Any]:
    """Private authenticated run-level entrypoint, no original document bodies.

    Authentication is enforced by the API router/middleware before invocation;
    this function additionally resolves run files only through validated
    run storage. It deliberately does not persist the quote or its result.
    """
    from fastapi import HTTPException

    from src.modules.tender_operator_agent_demo.upload_service import (
        _input_dir,
        _load_metadata,
        tender_processing_collection_id,
    )
    from src.shared.document_processing import process_document_bytes

    metadata = _load_metadata(run_id)
    file_record = next(
        (
            item for item in metadata.get("files", [])
            if isinstance(item, dict) and item.get("file_id") == file_id
        ),
        None,
    )
    if file_record is None:
        raise HTTPException(status_code=404, detail="Original file not found in run")
    result = attest_original_quote(
        input_root=_input_dir(run_id),
        file_record=file_record,
        exact_quote=exact_quote,
        collection_id=tender_processing_collection_id("upload"),
        processor=process_document_bytes,
    )
    if result is None:
        return {"status": "unverified", "evidence": None}
    return {"status": "literal_quote_found_in_extracted_original_only", "evidence": result}
