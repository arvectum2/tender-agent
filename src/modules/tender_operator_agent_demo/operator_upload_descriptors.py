"""Upload file metadata schema projection without filesystem side effects.

The public and legacy upload service share this exact descriptor shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _build_file_descriptor(
    *,
    file_id: str,
    original_name: str,
    stored_name: str,
    role_hint: str | None,
    size_bytes: int,
    content_type: str,
    source_type: str | None = None,
    source_url: str | None = None,
    document_kind: str | None = None,
    parent_archive: str | None = None,
) -> dict[str, Any]:
    return {
        "file_id": file_id,
        "original_name": original_name,
        "display_name": original_name,
        "stored_name": stored_name,
        "role_hint": role_hint,
        "extension": Path(stored_name).suffix.lower(),
        "size_bytes": size_bytes,
        "content_type": content_type or "application/octet-stream",
        "source": "upload",
        "source_type": source_type or "upload",
        "source_url": source_url,
        "document_kind": document_kind,
        "parent_archive": parent_archive,
        "extracted_text_available": False,
        "text_extraction_status": "pending",
        "warnings": [],
    }


def build_demo_file_descriptor(
    *,
    file_id: str,
    original_name: str,
    stored_name: str,
    role_hint: str | None = None,
    size_bytes: int,
    content_type: str,
    source: str = "upload",
    source_type: str | None = None,
    source_url: str | None = None,
    document_kind: str | None = None,
    parent_archive: str | None = None,
) -> dict[str, Any]:
    descriptor = _build_file_descriptor(
        file_id=file_id,
        original_name=original_name,
        stored_name=stored_name,
        role_hint=role_hint,
        size_bytes=size_bytes,
        content_type=content_type,
        source_type=source_type,
        source_url=source_url,
        document_kind=document_kind,
        parent_archive=parent_archive,
    )
    descriptor["source"] = source
    return descriptor
