from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.shared.db.base import Base
from src.tender_research.rag.data_platform import (
    DataPlatformClient,
    DataPlatformDocumentProjector,
    DataPlatformError,
    DataPlatformRagRetriever,
    DataPlatformTenderIndexer,
    build_legacy_tender_collection_id,
    build_tender_collection_id,
)
from src.tender_research.rag.presets import TENDER_SEARCH_PROFILE
from src.tender_research.repository import TenderRepository


def _repo() -> TenderRepository:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return TenderRepository(sessionmaker(bind=engine)())


def _seed_chunk(repo: TenderRepository, *, registry_number: str = "001"):
    tender = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": f"t-{registry_number}",
            "registry_number": registry_number,
            "title": f"Закупка {registry_number}",
            "customer_name": "Заказчик",
        }
    )
    document = repo.upsert_document(
        {
            "tender_id": tender.id,
            "file_name": "contract.txt",
        }
    )
    chunk = repo.upsert_document_chunk(
        {
            "tender_id": tender.id,
            "document_id": document.id,
            "chunk_index": 0,
            "text": "Оплата производится в течение семи дней после приемки.",
            "text_hash": "hash-1",
            "char_start": 0,
            "char_end": 58,
            "token_estimate": 10,
            "source_file_name": "contract.txt",
        }
    )
    repo._session.commit()
    return tender, document, chunk


class FakeDataPlatformClient:
    def __init__(
        self,
        *,
        process_text: str | None = None,
        process_metadata: dict | None = None,
    ) -> None:
        self.process_text = process_text
        self.process_metadata = process_metadata
        self.collections: list[tuple[str, str]] = []
        self.ingested: list[dict] = []
        self.search_requests: list[dict] = []
        self.search_hits: list[dict] = []
        self.collection_exists_responses: dict[str, bool] = {}

    def process_document(
        self,
        *,
        collection_id: str,
        canonical_uri: str,
        title: str,
        content: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        chunk_size_chars: int = 1500,
        overlap_chars: int = 200,
        min_chunk_chars: int = 120,
        max_chars: int = 2_000_000,
    ):
        self.ingested.append(
            {
                "operation": "process_document",
                "collection_id": collection_id,
                "canonical_uri": canonical_uri,
                "title": title,
                "filename": filename,
                "content": content,
            }
        )
        text = self.process_text if self.process_text is not None else content.decode("utf-8")
        metadata = (
            dict(self.process_metadata)
            if self.process_metadata is not None
            else {"file_name": filename}
        )
        return {
            "collection_id": collection_id,
            "resource_id": "platform-resource",
            "document_id": "platform-document",
            "canonical_uri": canonical_uri,
            "title": title,
            "media_type": content_type,
            "extraction_status": "extracted",
            "metadata": metadata,
            "text": text,
            "chunks": [
                {
                    "chunk_id": "platform-chunk-1",
                    "ordinal": 0,
                    "text": text,
                    "content_hash": "platform-hash-1",
                    "char_start": 0,
                    "char_end": len(text),
                    "token_estimate": max(1, len(text) // 4),
                }
            ],
        }

    def ensure_collection(self, *, collection_id: str, name: str, owner: str = "tender-agent"):
        self.collections.append((collection_id, name))
        return {"collection_id": collection_id, "owner": owner, "name": name}

    def ingest_chunk(self, *, collection_id: str, chunk_id: str, file_name: str, text: str):
        self.ingested.append(
            {
                "collection_id": collection_id,
                "chunk_id": chunk_id,
                "file_name": file_name,
                "text": text,
            }
        )
        return {"chunks": 1, "embeddings": 1}

    def collection_stats(self, collection_id: str):
        return {
            "collection_id": collection_id,
            "resources": 1,
            "documents": 1,
            "chunks": 1,
            "embeddings": 1,
        }

    def collection_exists(self, collection_id: str) -> bool:
        return self.collection_exists_responses.get(collection_id, True)

    def search_with_profile(
        self,
        *,
        query: str,
        collections: list[str],
        limit: int,
        profile: dict,
    ):
        self.search_requests.append(
            {
                "query": query,
                "collections": list(collections),
                "limit": limit,
                "profile": dict(profile),
            }
        )
        return list(self.search_hits)



def test_projector_uses_data_platform_for_extraction_and_chunking(tmp_path) -> None:
    from src.tender_research.config import TenderResearchConfig

    repo = _repo()
    tender = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "t-projection",
            "registry_number": "DP-PROJECTION",
            "title": "Projection test",
        }
    )
    source = tmp_path / "contract.txt"
    source.write_text("Оплата производится после приемки.", encoding="utf-8")
    document = repo.upsert_document(
        {
            "tender_id": tender.id,
            "file_name": "contract.txt",
            "local_path": str(source),
            "content_type": "text/plain",
            "download_status": "downloaded",
            "text_extraction_status": "pending",
        }
    )
    repo._session.commit()
    client = FakeDataPlatformClient()

    summary = DataPlatformDocumentProjector(
        repo,
        client,
        TenderResearchConfig(data_dir=str(tmp_path)),
    ).build_for_tender(tender)

    assert summary.documents_processed == 1
    assert summary.extracted_documents == 1
    assert summary.chunks_projected == 1
    repo._session.refresh(document)
    assert document.text_extraction_status == "extracted"
    assert document.extracted_text_path
    chunks = repo.list_document_chunks(document.id)
    assert len(chunks) == 1
    assert chunks[0].raw_meta["source"] == "data_platform_projection"
    assert chunks[0].raw_meta["data_platform"]["chunk_id"] == "platform-chunk-1"
    processing = document.raw_meta["data_platform_processing"]
    assert processing["metadata"]["file_name"] == "contract.txt"
    assert processing["ocr_review"]["ocr_used"] is False
    assert processing["ocr_review"]["requires_review"] is False
    assert client.ingested[0]["operation"] == "process_document"


def test_projector_preserves_ocr_provenance_and_routes_low_confidence_to_review(
    tmp_path,
) -> None:
    from src.tender_research.config import TenderResearchConfig

    repo = _repo()
    tender = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "t-ocr-projection",
            "registry_number": "DP-OCR",
            "title": "OCR projection test",
        }
    )
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF-synthetic-scan")
    document = repo.upsert_document(
        {
            "tender_id": tender.id,
            "file_name": "scan.pdf",
            "local_path": str(source),
            "content_type": "application/pdf",
            "download_status": "downloaded",
            "text_extraction_status": "pending",
            "raw_meta": {"revision": 3},
        }
    )
    repo._session.commit()
    client = FakeDataPlatformClient(
        process_text="Техническое задание",
        process_metadata={
            "pdf_pages": [
                {"page_number": 1, "native_char_count": 0, "needs_ocr": True}
            ],
            "ocr": {
                "provider": "tesseract",
                "page_numbers": [1],
                "mean_confidence": 86.89,
                "pages": [
                    {
                        "page_number": 1,
                        "confidence": 86.89,
                        "regions": [
                            {
                                "text": "Техническое",
                                "confidence": 87.5,
                                "left": 10,
                                "top": 20,
                                "width": 140,
                                "height": 30,
                            }
                        ],
                    }
                ],
            },
            "vlm": [],
        },
    )

    summary = DataPlatformDocumentProjector(
        repo,
        client,
        TenderResearchConfig(data_dir=str(tmp_path)),
    ).build_for_tender(tender)

    assert summary.extracted_documents == 1
    repo._session.refresh(document)
    assert document.raw_meta["revision"] == 3
    processing = document.raw_meta["data_platform_processing"]
    assert processing["metadata_available"] is True
    assert processing["metadata"]["ocr"]["provider"] == "tesseract"
    region = processing["metadata"]["ocr"]["pages"][0]["regions"][0]
    assert region == {
        "text": "Техническое",
        "confidence": 87.5,
        "left": 10,
        "top": 20,
        "width": 140,
        "height": 30,
    }
    assert processing["ocr_review"] == {
        "ocr_used": True,
        "requires_review": True,
        "reason": "ocr_low_confidence",
        "provider": "tesseract",
        "mean_confidence": 86.89,
        "review_below_confidence": 90.0,
    }


def test_projector_fails_closed_when_ocr_confidence_is_missing(tmp_path) -> None:
    from src.tender_research.config import TenderResearchConfig

    repo = _repo()
    tender = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "t-ocr-no-confidence",
            "registry_number": "DP-OCR-NO-CONF",
            "title": "OCR missing confidence",
        }
    )
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF-synthetic-scan")
    document = repo.upsert_document(
        {
            "tender_id": tender.id,
            "file_name": "scan.pdf",
            "local_path": str(source),
            "content_type": "application/pdf",
            "download_status": "downloaded",
            "text_extraction_status": "pending",
        }
    )
    repo._session.commit()
    client = FakeDataPlatformClient(
        process_text="Распознанный текст",
        process_metadata={
            "ocr": {
                "provider": "tesseract",
                "page_numbers": [1],
                "mean_confidence": None,
                "pages": [],
            }
        },
    )

    DataPlatformDocumentProjector(
        repo,
        client,
        TenderResearchConfig(data_dir=str(tmp_path)),
    ).build_for_tender(tender)

    repo._session.refresh(document)
    review = document.raw_meta["data_platform_processing"]["ocr_review"]
    assert review["ocr_used"] is True
    assert review["requires_review"] is True
    assert review["reason"] == "ocr_confidence_missing"


def test_projector_migrates_legacy_chunks_without_changing_local_chunk_id(tmp_path) -> None:
    from src.tender_research.config import TenderResearchConfig

    repo = _repo()
    tender = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "t-legacy-projection",
            "registry_number": "DP-LEGACY",
            "title": "Legacy projection test",
        }
    )
    source = tmp_path / "legacy-contract.txt"
    source.write_text("Оплата производится после приемки.", encoding="utf-8")
    text_path = tmp_path / "legacy-extracted.txt"
    text_path.write_text("Оплата производится после приемки.", encoding="utf-8")
    document = repo.upsert_document(
        {
            "tender_id": tender.id,
            "file_name": "legacy-contract.txt",
            "local_path": str(source),
            "content_type": "text/plain",
            "download_status": "downloaded",
            "text_extraction_status": "extracted",
            "extracted_text_path": str(text_path),
            "extracted_text_chars": len("Оплата производится после приемки."),
        }
    )
    legacy_chunk = repo.upsert_document_chunk(
        {
            "tender_id": tender.id,
            "document_id": document.id,
            "chunk_index": 0,
            "text": "Оплата производится после приемки.",
            "text_hash": "platform-hash-1",
            "char_start": 0,
            "char_end": len("Оплата производится после приемки."),
            "token_estimate": 8,
            "source_file_name": document.file_name,
            "source_text_path": str(text_path),
            "raw_meta": {"source": "extracted_text"},
        }
    )
    original_chunk_id = legacy_chunk.id
    repo._session.commit()
    client = FakeDataPlatformClient()

    summary = DataPlatformDocumentProjector(
        repo,
        client,
        TenderResearchConfig(data_dir=str(tmp_path)),
    ).build_for_tender(tender)

    assert summary.documents_processed == 1
    chunks = repo.list_document_chunks(document.id)
    assert len(chunks) == 1
    assert chunks[0].id == original_chunk_id
    assert chunks[0].raw_meta["source"] == "data_platform_projection"
    assert client.ingested[0]["operation"] == "process_document"


def test_collection_id_changes_when_chunk_revision_changes() -> None:
    repo = _repo()
    tender, _document, chunk = _seed_chunk(repo)

    first = build_tender_collection_id(repo, tender.id)
    chunk.text_hash = "hash-2"
    repo._session.commit()
    second = build_tender_collection_id(repo, tender.id)

    assert first
    assert second
    assert first != second
    assert first.startswith(f"tender:{tender.id}:")


def test_retriever_falls_back_to_legacy_tender_collection() -> None:
    repo = _repo()
    tender, _document, chunk = _seed_chunk(repo)
    client = FakeDataPlatformClient()
    canonical = build_tender_collection_id(repo, tender.id)
    legacy = build_legacy_tender_collection_id(repo, tender.id)
    assert canonical is not None
    assert legacy is not None
    client.collection_exists_responses = {canonical: False, legacy: True}
    client.search_hits = [
        {
            "canonical_uri": f"tender-chunk://{chunk.id}",
            "scores": {"fusion": 0.5},
        }
    ]

    hits = DataPlatformRagRetriever(repo, client).search_documents(
        "оплата", registry_number="001", limit=5
    )

    assert len(hits) == 1
    assert client.search_requests[0]["collections"] == [legacy]
    assert client.search_requests[0]["profile"] == TENDER_SEARCH_PROFILE


def test_indexer_creates_versioned_collection_and_ingests_chunks() -> None:
    repo = _repo()
    tender, _document, chunk = _seed_chunk(repo)
    client = FakeDataPlatformClient()

    summary = DataPlatformTenderIndexer(repo, client).build_for_tender(tender.id)

    assert summary.collection_id == build_tender_collection_id(repo, tender.id)
    assert summary.chunks_seen == 1
    assert summary.chunks_indexed == 1
    assert summary.platform_chunks_created == 1
    assert summary.embeddings_created == 1
    assert client.collections == [
        (summary.collection_id, "Tender 001"),
    ]
    assert client.ingested[0]["chunk_id"] == chunk.id
    assert client.ingested[0]["file_name"] == "contract.txt"


def test_retriever_maps_platform_hit_back_to_tender_chunk() -> None:
    repo = _repo()
    tender, document, chunk = _seed_chunk(repo)
    client = FakeDataPlatformClient()
    client.search_hits = [
        {
            "canonical_uri": f"tender-chunk://{chunk.id}",
            "scores": {
                "lexical": 0.4,
                "vector": 0.8,
                "fusion": 0.031,
            },
        }
    ]

    hits = DataPlatformRagRetriever(repo, client).search_documents(
        "порядок оплаты",
        registry_number="001",
        limit=5,
    )

    assert len(hits) == 1
    hit = hits[0]
    assert hit.chunk_id == chunk.id
    assert hit.document_id == document.id
    assert hit.tender_id == tender.id
    assert hit.file_name == "contract.txt"
    assert hit.score == pytest.approx(0.031)
    assert client.search_requests[0]["profile"] == TENDER_SEARCH_PROFILE
    assert client.search_requests[0]["collections"] == [
        build_tender_collection_id(repo, tender.id)
    ]


def test_retriever_does_not_search_unknown_tender() -> None:
    repo = _repo()
    client = FakeDataPlatformClient()

    hits = DataPlatformRagRetriever(repo, client).search_documents(
        "оплата",
        registry_number="missing",
    )

    assert hits == []
    assert client.search_requests == []


def test_http_client_uses_canonical_tender_chunk_uri() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/collections/test-collection":
            return httpx.Response(404, json={"detail": "not found"})
        if request.url.path == "/v1/collections":
            return httpx.Response(
                200,
                json={
                    "collection_id": "test-collection",
                    "owner": "tender-agent",
                    "name": "Tender 001",
                },
            )
        if request.url.path == "/v1/collections/test-collection/stats":
            return httpx.Response(
                200,
                json={
                    "collection_id": "test-collection",
                    "resources": 1,
                    "documents": 1,
                    "chunks": 1,
                    "embeddings": 1,
                },
            )
        if request.url.path == "/v1/ingest/document":
            captured["body"] = request.read().decode("utf-8", errors="replace")
            return httpx.Response(
                200,
                json={
                    "collection_id": "test-collection",
                    "resource_id": "r1",
                    "document_id": "d1",
                    "chunks": 1,
                    "embeddings": 1,
                    "canonical_uri": "tender-chunk://chunk-1",
                },
            )
        raise AssertionError(request.url)

    http_client = httpx.Client(
        base_url="http://data-platform.test",
        transport=httpx.MockTransport(handler),
    )
    client = DataPlatformClient(
        base_url="http://data-platform.test",
        api_key="secret",
        client=http_client,
    )

    client.ensure_collection(collection_id="test-collection", name="Tender 001")
    result = client.ingest_chunk(
        collection_id="test-collection",
        chunk_id="chunk-1",
        file_name="contract.txt",
        text="Оплата после приемки",
    )

    stats = client.collection_stats("test-collection")
    assert stats["resources"] == 1
    assert stats["embeddings"] == 1
    assert result["canonical_uri"] == "tender-chunk://chunk-1"
    assert 'name="canonical_uri"' in captured["body"]
    assert "tender-chunk://chunk-1" in captured["body"]
    assert 'name="pre_chunked"' in captured["body"]
    assert "true" in captured["body"]





def test_http_client_processes_raw_document_in_data_platform() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/process/document":
            captured["body"] = request.read().decode("utf-8", errors="replace")
            return httpx.Response(
                200,
                json={
                    "collection_id": "tender:tender-1:processing",
                    "resource_id": "r1",
                    "document_id": "d1",
                    "canonical_uri": "tender-document://doc-1",
                    "title": "contract.txt",
                    "media_type": "text/plain",
                    "extraction_status": "extracted",
                    "text": "raw tender document",
                    "chunks": [],
                },
            )
        raise AssertionError(request.url)

    client = DataPlatformClient(
        base_url="http://data-platform.test",
        client=httpx.Client(
            base_url="http://data-platform.test",
            transport=httpx.MockTransport(handler),
        ),
    )
    result = client.process_document(
        collection_id="tender:tender-1:processing",
        canonical_uri="tender-document://doc-1",
        title="contract.txt",
        content=b"raw tender document",
        filename="contract.txt",
        content_type="text/plain",
    )

    assert result["extraction_status"] == "extracted"
    assert 'name="chunk_size_chars"' in captured["body"]
    assert "raw tender document" in captured["body"]


def test_http_client_uses_semantic_first_hybrid_weights() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/search":
            captured["payload"] = json.loads(request.read().decode("utf-8"))
            return httpx.Response(200, json={"query": "оплата", "hits": []})
        raise AssertionError(request.url)

    client = DataPlatformClient(
        base_url="http://data-platform.test",
        client=httpx.Client(
            base_url="http://data-platform.test",
            transport=httpx.MockTransport(handler),
        ),
    )

    assert client.search_with_profile(
        query="оплата",
        collections=["tender:x:y"],
        limit=5,
        profile=TENDER_SEARCH_PROFILE,
    ) == []
    assert captured["payload"]["mode"] == "hybrid"
    assert captured["payload"]["lexical_weight"] == 1.0
    assert captured["payload"]["vector_weight"] == 4.0

def test_http_client_fails_closed_without_legacy_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="platform unavailable")

    client = DataPlatformClient(
        base_url="http://data-platform.test",
        client=httpx.Client(
            base_url="http://data-platform.test",
            transport=httpx.MockTransport(handler),
        ),
    )

    with pytest.raises(DataPlatformError, match="HTTP 503"):
        client.search(query="оплата", collections=["tender:x:y"], limit=5)


def test_prepare_service_uses_data_platform_without_legacy_embeddings(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from src.tender_research.config import TenderResearchConfig
    from src.tender_research.rag.data_platform import DataPlatformIndexSummary
    from src.tender_research.rag.prepare_service import prepare_tender_for_analysis

    tender = MagicMock()
    tender.id = "tender-dp"
    tender.registry_number = "DP-001"
    document = MagicMock()
    document.download_status = "downloaded"
    document.text_extraction_status = "extracted"
    document.extracted_text_path = "/tmp/doc.txt"
    tender.documents = [document]

    repo = MagicMock()
    repo.get_tender_by_registry_number.return_value = tender
    repo.count_chunks_by_tender.return_value = 2
    repo.count_extracted_documents_by_tender.return_value = 1

    config = TenderResearchConfig(rag_retrieval_backend="data_platform")
    platform_client = MagicMock()
    platform_client.__enter__.return_value = platform_client
    platform_client.__exit__.return_value = None
    indexer = MagicMock()
    indexer.build_for_tender.return_value = DataPlatformIndexSummary(
        collection_id="tender:tender-dp:rev",
        chunks_seen=2,
        chunks_indexed=2,
        platform_chunks_created=2,
        embeddings_created=2,
    )

    monkeypatch.setattr(
        "src.tender_research.rag.prepare_service.TenderRepository",
        lambda session: repo,
    )
    monkeypatch.setattr(
        "src.tender_research.rag.prepare_service.load_config",
        lambda: config,
    )
    monkeypatch.setattr(
        "src.tender_research.rag.prepare_service.download_tender_documents",
        lambda *args, **kwargs: {"downloaded": 0, "failed": 0},
    )
    monkeypatch.setattr(
        "src.tender_research.rag.prepare_service.build_data_platform_client",
        lambda _config: platform_client,
    )
    monkeypatch.setattr(
        "src.tender_research.rag.prepare_service.DataPlatformTenderIndexer",
        lambda *_args, **_kwargs: indexer,
    )
    projector = MagicMock()
    projector.build_for_tender.return_value = MagicMock(
        documents_processed=0,
        chunks_projected=0,
        chunks_pruned=0,
    )
    monkeypatch.setattr(
        "src.tender_research.rag.prepare_service.DataPlatformDocumentProjector",
        lambda *_args, **_kwargs: projector,
    )


    result = prepare_tender_for_analysis("DP-001", session=MagicMock())

    assert result.ready_for_analysis is True
    assert result.embeddings_total == 2
    indexer.build_for_tender.assert_called_once_with("tender-dp")


def test_analysis_service_uses_data_platform_without_legacy_retriever(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from src.tender_research.config import TenderResearchConfig
    from src.tender_research.rag.analysis_service import analyze_tender

    tender = MagicMock()
    tender.id = "tender-dp"
    tender.registry_number = "DP-001"

    repo = MagicMock()
    repo.get_tender_by_registry_number.return_value = tender
    repo.count_chunks_by_tender.return_value = 1

    config = TenderResearchConfig(rag_retrieval_backend="data_platform")
    platform_client = MagicMock()
    platform_client.collection_stats.return_value = {
        "resources": 1,
        "documents": 1,
        "chunks": 1,
        "embeddings": 1,
    }
    retriever = MagicMock()
    retriever.search_documents.return_value = []

    monkeypatch.setattr(
        "src.tender_research.rag.analysis_service.TenderRepository",
        lambda session: repo,
    )
    monkeypatch.setattr(
        "src.tender_research.rag.analysis_service.load_config",
        lambda: config,
    )
    monkeypatch.setattr(
        "src.tender_research.rag.analysis_service.build_tender_collection_id",
        lambda *_args: "tender:tender-dp:rev",
    )
    monkeypatch.setattr(
        "src.tender_research.rag.analysis_service.build_data_platform_client",
        lambda _config: platform_client,
    )
    monkeypatch.setattr(
        "src.tender_research.rag.analysis_service.DataPlatformRagRetriever",
        lambda *_args: retriever,
    )


    result = analyze_tender(
        registry_number="DP-001",
        session=MagicMock(),
        use_llm=False,
        record_history=False,
    )

    assert result.retrieval_provider == "data_platform"
    assert result.retrieval_model == "hybrid"
    assert retriever.search_documents.call_count > 0
    platform_client.close.assert_called_once()


def test_analysis_service_fails_closed_when_platform_index_is_unavailable(
    monkeypatch,
) -> None:
    from unittest.mock import MagicMock

    from src.tender_research.config import TenderResearchConfig
    from src.tender_research.rag.analysis_service import analyze_tender

    tender = MagicMock()
    tender.id = "tender-dp"
    tender.registry_number = "DP-001"

    repo = MagicMock()
    repo.get_tender_by_registry_number.return_value = tender
    repo.count_chunks_by_tender.return_value = 1

    config = TenderResearchConfig(rag_retrieval_backend="data_platform")
    platform_client = MagicMock()
    platform_client.collection_stats.side_effect = DataPlatformError(
        "platform unavailable"
    )

    monkeypatch.setattr(
        "src.tender_research.rag.analysis_service.TenderRepository",
        lambda session: repo,
    )
    monkeypatch.setattr(
        "src.tender_research.rag.analysis_service.load_config",
        lambda: config,
    )
    monkeypatch.setattr(
        "src.tender_research.rag.analysis_service.build_tender_collection_id",
        lambda *_args: "tender:tender-dp:rev",
    )
    monkeypatch.setattr(
        "src.tender_research.rag.analysis_service.build_data_platform_client",
        lambda _config: platform_client,
    )


    result = analyze_tender(
        registry_number="DP-001",
        session=MagicMock(),
        use_llm=False,
        record_history=False,
    )

    # A transport outage is not a missing index or absent document context.
    assert result.status == "failed"
    assert any("Data Platform collection status unavailable" in error for error in result.errors)
    assert not any("Run tender preparation first" in error for error in result.errors)
    platform_client.close.assert_called_once()


def test_cli_retrieval_runtime_skips_legacy_embedding_provider(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from src.tender_research.config import TenderResearchConfig
    from src.tender_research.rag import cli

    session = MagicMock()
    repo = MagicMock()
    platform_client = MagicMock()

    monkeypatch.setattr(cli, "_get_session", lambda: session)
    monkeypatch.setattr(cli, "TenderRepository", lambda _session: repo)
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: TenderResearchConfig(rag_retrieval_backend="data_platform"),
    )
    monkeypatch.setattr(cli, "_apply_runtime_overrides", lambda *_args: None)
    monkeypatch.setattr(
        cli,
        "build_data_platform_client",
        lambda _config: platform_client,
    )


    (
        returned_session,
        returned_repo,
        config,
        provider,
        vector_store,
        retriever,
    ) = cli._build_runtime(retrieval_only=True)

    assert returned_session is session
    assert returned_repo is repo
    assert config.rag_retrieval_backend == "data_platform"
    assert provider is None
    assert vector_store is None
    retriever.close()
    platform_client.close.assert_called_once()
