"""Bounded document-to-Data-Platform extraction adapter for operator intake.

Keep transport/extraction in Data Platform, and inject the generic consumer
to preserve legacy monkeypatch and configuration contracts. No OCR/LLM here.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

from src.shared.data_platform import DataPlatformError
from src.shared.document_processing import (
    EXTRACTED_STATUS,
    UNSUPPORTED_STATUS,
    ProcessedDocument,
)


def extract_operator_document(
    *,
    file_name: str,
    content: bytes,
    collection_id: str,
    processor: Callable[..., ProcessedDocument],
) -> tuple[str | None, list[str], str, ProcessedDocument | None]:
    warnings: list[str] = []
    processed: ProcessedDocument | None = None
    try:
        processed = processor(
            content=content,
            filename=file_name,
            collection_id=collection_id,
            canonical_uri=f"tender-upload://{hashlib.sha256(content).hexdigest()}",
            min_chunk_chars=1,
        )
        status = processed.extraction_status
        text = processed.text.strip() or None
    except (DataPlatformError, ValueError, OSError):
        status = "failed"
        text = None

    if status == UNSUPPORTED_STATUS:
        warnings.append(
            f"Извлечение текста для {Path(file_name).suffix.lower()} пока не поддерживается."
        )
    elif status != EXTRACTED_STATUS and not text:
        warnings.append(f"Не удалось извлечь текст из {Path(file_name).name}.")
    return text, warnings, status, processed
