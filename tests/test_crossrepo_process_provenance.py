"""Consumer regressions: generic Data Platform identities survive in Tender Agent."""

from __future__ import annotations

import hashlib

from src.shared.document_processing import (
    ProcessedChunk,
    ProcessedDocument,
    process_document_bytes,
)


class _Client:
    def __init__(self, output: dict):
        self.output = output
        self.calls: list[dict] = []

    def process_document(self, **kwargs):
        self.calls.append(kwargs)
        return self.output


def test_platform_document_provenance_is_preserved_without_local_reindexing():
    text = "Требование: обеспечить резервное копирование данных."
    data = text.encode()
    digest = hashlib.sha256(data).hexdigest()
    client = _Client({
        "resource_id": "resource-from-platform",
        "document_id": "document-from-platform",
        "canonical_uri": f"content-sha256://{digest}",
        "extraction_status": "extracted",
        "metadata": {"source_page": 2, "ocr_engine": "configured-model"},
        "text": text,
        "chunks": [{
            "chunk_id": "source-linked-chunk-01",
            "ordinal": 0,
            "text": text,
            "content_hash": digest,
            "char_start": 0,
            "char_end": len(text),
            "token_estimate": 7,
        }],
    })
    result = process_document_bytes(
        content=data,
        filename="тз.txt",
        collection_id="tender-source",
        client=client,
    )
    assert isinstance(result, ProcessedDocument)
    assert result.extraction_status == "extracted"
    assert result.resource_id == "resource-from-platform"
    assert result.document_id == "document-from-platform"
    assert result.canonical_uri == f"content-sha256://{digest}"
    assert result.metadata == {"source_page": 2, "ocr_engine": "configured-model"}
    assert result.chunks[0].chunk_id == "source-linked-chunk-01"
    assert result.chunks[0].char_start == 0
    assert client.calls[0]["content"] == data


def test_legacy_adapter_is_compatible_with_optional_provenance():
    chunk = ProcessedChunk(0, "текст", "hash", 0, 5, 1)
    old_result = ProcessedDocument("extracted", "текст", (chunk,))
    assert old_result.resource_id is None
    assert old_result.document_id is None
    assert old_result.metadata == {}
    assert old_result.chunks[0].chunk_id is None


def test_missing_platform_identity_never_gets_invented():
    client = _Client({
        "extraction_status": "empty",
        "text": "",
        "metadata": None,
        "chunks": [],
    })
    result = process_document_bytes(
        content=b"",
        filename="empty.txt",
        collection_id="test",
        client=client,
    )
    assert result.resource_id is None
    assert result.document_id is None
    assert result.chunks == ()
    assert result.extraction_status == "empty"
    assert result.metadata == {}
