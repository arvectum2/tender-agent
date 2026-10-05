from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.shared.config.settings import Settings
from src.shared.document_processing import process_document_bytes


def _settings() -> Settings:
    return Settings(
        rag_retrieval_backend="data_platform",
        rag_data_platform_base_url="http://data-platform.test",
        rag_chunk_size_chars=1000,
        rag_chunk_overlap_chars=100,
        rag_min_chunk_chars=20,
        document_extract_max_chars=50_000,
    )


def test_process_document_bytes_maps_platform_contract() -> None:
    client = MagicMock()
    client.process_document.return_value = {
        "extraction_status": "extracted",
        "text": "procurement text",
        "chunks": [
            {
                "ordinal": 0,
                "text": "procurement text",
                "content_hash": "abc123",
                "char_start": 0,
                "char_end": 16,
                "token_estimate": 4,
            }
        ],
    }

    result = process_document_bytes(
        content=b"payload",
        filename="notice.xml",
        collection_id="test:processing",
        settings=_settings(),
        client=client,
    )

    assert result.extraction_status == "extracted"
    assert result.text == "procurement text"
    assert len(result.chunks) == 1
    assert result.chunks[0].index == 0
    assert result.chunks[0].text_hash == "abc123"
    kwargs = client.process_document.call_args.kwargs
    assert kwargs["chunk_size_chars"] == 1000
    assert kwargs["overlap_chars"] == 100
    assert kwargs["min_chunk_chars"] == 20
    assert kwargs["max_chars"] == 50_000


def test_process_document_bytes_validates_chunk_policy_before_request() -> None:
    client = MagicMock()
    with pytest.raises(ValueError, match="overlap_chars"):
        process_document_bytes(
            content=b"payload",
            filename="notice.xml",
            collection_id="test:processing",
            chunk_size_chars=100,
            overlap_chars=100,
            settings=_settings(),
            client=client,
        )
    client.process_document.assert_not_called()


def test_injected_client_is_not_closed() -> None:
    client = MagicMock()
    client.process_document.return_value = {
        "extraction_status": "empty",
        "text": "",
        "chunks": [],
    }

    process_document_bytes(
        content=b"",
        filename="empty.txt",
        collection_id="test:processing",
        settings=_settings(),
        client=client,
    )

    client.close.assert_not_called()
