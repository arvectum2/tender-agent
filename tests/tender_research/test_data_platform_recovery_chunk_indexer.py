from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.shared.db.base import Base
from src.tender_research.config import TenderResearchConfig
from src.tender_research.rag.data_platform import (
    DataPlatformError,
    DataPlatformRecoveryChunkIndexer,
    extract_document_with_data_platform,
)
from src.tender_research.repository import TenderRepository


class FakeDataPlatformClient:
    def __init__(self, *, extracted_text: str) -> None:
        self.extracted_text = extracted_text
        self.requests: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def process_document(self, **kwargs):
        self.requests.append(dict(kwargs))
        text = self.extracted_text
        return {
            "collection_id": kwargs["collection_id"],
            "resource_id": "platform-resource",
            "document_id": "platform-document",
            "canonical_uri": kwargs["canonical_uri"],
            "title": kwargs["title"],
            "media_type": "text/plain",
            "extraction_status": "extracted",
            "text": text,
            "chunks": [
                {
                    "chunk_id": "platform-chunk-1",
                    "ordinal": 0,
                    "text": text,
                    "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "char_start": 0,
                    "char_end": len(text),
                    "token_estimate": max(1, len(text) // 4),
                }
            ],
        }


def _repo() -> TenderRepository:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return TenderRepository(sessionmaker(bind=engine)())


def _seed_document(repo: TenderRepository, tmp_path: Path, text: str):
    tender = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "recovery",
            "registry_number": "RECOVERY-1",
            "title": "Recovery",
        }
    )
    source = tmp_path / "contract.txt"
    extracted = tmp_path / "contract.extracted.txt"
    source.write_text(text, encoding="utf-8")
    extracted.write_text(text, encoding="utf-8")
    document = repo.upsert_document(
        {
            "tender_id": tender.id,
            "file_name": "contract.txt",
            "local_path": str(source),
            "content_type": "text/plain",
            "download_status": "downloaded",
            "text_extraction_status": "extracted",
            "extracted_text_path": str(extracted),
            "extracted_text_chars": len(text),
        }
    )
    repo._session.commit()
    return tender, document


def test_recovery_chunk_builder_projects_platform_chunks_idempotently(
    tmp_path: Path,
) -> None:
    text = "Оплата производится после приемки."
    repo = _repo()
    tender, document = _seed_document(repo, tmp_path, text)
    client = FakeDataPlatformClient(extracted_text=text)
    indexer = DataPlatformRecoveryChunkIndexer(
        repo,
        TenderResearchConfig(data_dir=str(tmp_path)),
        client_factory=lambda _config: client,
    )

    first = indexer.build_for_tender(tender.id, commit=False)
    chunks = repo.list_document_chunks(document.id)
    assert first["chunks_created"] == 1
    assert len(chunks) == 1
    chunk_id = chunks[0].id
    assert chunks[0].raw_meta["source"] == "data_platform_recovery_projection"

    second = indexer.build_for_tender(tender.id, commit=False)
    chunks = repo.list_document_chunks(document.id)
    assert second["chunks_created"] == 0
    assert second["chunks_skipped_existing"] == 1
    assert len(chunks) == 1
    assert chunks[0].id == chunk_id
    assert len(client.requests) == 2


def test_recovery_chunk_builder_fails_closed_on_extraction_mismatch(
    tmp_path: Path,
) -> None:
    repo = _repo()
    tender, _document = _seed_document(repo, tmp_path, "authoritative text")
    client = FakeDataPlatformClient(extracted_text="different text")
    indexer = DataPlatformRecoveryChunkIndexer(
        repo,
        TenderResearchConfig(data_dir=str(tmp_path)),
        client_factory=lambda _config: client,
    )

    with pytest.raises(DataPlatformError, match="extraction mismatch"):
        indexer.build_for_tender(tender.id, commit=False)


def test_recovery_extraction_adapter_uses_data_platform(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("platform extracted text", encoding="utf-8")
    document = SimpleNamespace(
        id="document-extract",
        local_path=str(source),
        file_name="source.txt",
        text_extraction_status="pending",
        extracted_text_path=None,
        extracted_text_chars=None,
    )
    client = FakeDataPlatformClient(extracted_text="platform extracted text")
    output_dir = tmp_path / "extracted"

    extract_document_with_data_platform(
        document,
        output_dir,
        TenderResearchConfig(data_dir=str(tmp_path)),
        client_factory=lambda _config: client,
    )

    assert document.text_extraction_status == "extracted"
    assert document.extracted_text_chars == len("platform extracted text")
    assert Path(document.extracted_text_path).read_text(encoding="utf-8") == (
        "platform extracted text"
    )
    assert client.requests[0]["content"] == b"platform extracted text"
