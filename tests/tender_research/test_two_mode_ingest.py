"""Pure isolated DB + fake SDK acceptance for opt-in two-mode RAG ingestion."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.shared.data_platform import DataPlatformError
from src.shared.db.base import Base
from src.tender_research.rag.data_platform import DataPlatformIndexSummary
from src.tender_research.rag.two_mode_ingest import (
    AsyncTenderIndexBatch,
    AsyncTenderIndexPending,
    TwoModeTenderIndexer,
)
from src.tender_research.repository import TenderRepository


class FakeClient:
    def __init__(self) -> None:
        self.collections: list[str] = []
        self.synchronous: list[str] = []
        self.queued: list[dict] = []
        self.jobs: dict[str, dict] = {}

    def ensure_collection(self, *, collection_id: str, **kwargs) -> dict:
        self.collections.append(collection_id)
        return {"collection_id": collection_id}

    def ingest_chunk(self, *, collection_id: str, chunk_id: str, **kwargs) -> dict:
        self.synchronous.append(chunk_id)
        return {"chunks": 1, "embeddings": 1}

    def enqueue_ingest_document_bytes(self, **kwargs) -> dict:
        self.queued.append(kwargs)
        job_id = f"job-{len(self.queued)}"
        receipt = {
            "job_id": job_id,
            "collection_id": kwargs["collection_id"],
            "status": "queued",
            "attempts": 0,
            "result": None,
        }
        self.jobs[job_id] = receipt
        return receipt

    def get_ingest_job(self, *, collection_id: str, job_id: str) -> dict:
        assert self.jobs[job_id]["collection_id"] == collection_id
        return dict(self.jobs[job_id])

    def complete_all(self) -> None:
        for job_id, row in self.jobs.items():
            self.jobs[job_id] = {
                **row,
                "status": "completed",
                "result": {
                    "resource_id": f"r-{job_id}",
                    "document_id": f"d-{job_id}",
                    "chunks": 1,
                },
            }


class FakeRetriever:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def search_documents(self, query: str, *, tender_id: str, limit: int):
        self.calls.append({"query": query, "tender_id": tender_id, "limit": limit})
        return [{"chunk_id": "evidence-verified", "score": 0.98}]


def seeded_repo(count: int) -> tuple[TenderRepository, str]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    repo = TenderRepository(sessionmaker(bind=engine)())
    tender = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "synthetic-async",
            "registry_number": "SYNTHETIC-ASYNC",
            "title": "Synthetic tender",
        }
    )
    doc = repo.upsert_document(
        {
            "tender_id": tender.id,
            "file_name": "synthetic.txt",
        }
    )
    for i in range(count):
        source = f"Синтетические условия приёмки документа номер {i:03d}."
        repo.upsert_document_chunk(
            {
                "tender_id": tender.id,
                "document_id": doc.id,
                "chunk_index": i,
                "text": source,
                "text_hash": hashlib.sha256(source.encode()).hexdigest(),
                "char_start": i * 50,
                "char_end": (i + 1) * 50,
                "token_estimate": 10,
                "source_file_name": "synthetic.txt",
            }
        )
    repo._session.commit()
    return repo, str(tender.id)


def test_default_uses_unchanged_sync_route() -> None:
    repo, tender_id = seeded_repo(9)
    client = FakeClient()
    pilot = TwoModeTenderIndexer(repo, client)
    assert pilot.mode(tender_id) == "synchronous"
    result = pilot.start(tender_id)
    assert isinstance(result, DataPlatformIndexSummary)
    assert result.chunks_indexed == 9
    assert len(client.synchronous) == 9 and client.queued == []


def test_opt_in_small_stays_sync_but_nine_chunks_use_background_in_waves() -> None:
    repo, tender_id = seeded_repo(9)
    client = FakeClient()
    pilot = TwoModeTenderIndexer(repo, client, async_enabled=True)
    assert pilot.mode(tender_id) == "background"
    first = pilot.start(tender_id)
    assert isinstance(first, AsyncTenderIndexBatch)
    assert len(first.receipts) == 8 and first.next_offset == 8
    assert client.synchronous == []
    assert all(
        item["canonical_uri"].startswith("tender-chunk://") for item in client.queued
    )
    assert all(item["pre_chunked"] for item in client.queued)
    assert all(len(item["idempotency_key"]) == 64 for item in client.queued)

    retriever = FakeRetriever()
    with pytest.raises(AsyncTenderIndexPending):
        pilot.search_when_ready(tender_id, [first], retriever, query="поставка")
    assert not retriever.calls
    second = pilot.start(tender_id, offset=first.next_offset)
    assert len(second.receipts) == 1 and second.next_offset is None
    with pytest.raises(AsyncTenderIndexPending):
        pilot.search_when_ready(tender_id, [first, second], retriever, query="поставка")
    assert not retriever.calls

    client.complete_all()
    assert pilot.require_ready(tender_id, [first, second]) == first.collection_id
    hits = pilot.search_when_ready(
        tender_id, [first, second], retriever, query="поставка"
    )
    assert hits[0]["chunk_id"] == "evidence-verified" and len(retriever.calls) == 1
    assert all(x == first.collection_id for x in client.collections)


@pytest.mark.parametrize("terminal", ["dead_letter", "cancelled"])
def test_terminal_job_failure_prevents_search(terminal: str) -> None:
    repo, tender_id = seeded_repo(9)
    client = FakeClient()
    pilot = TwoModeTenderIndexer(repo, client, async_enabled=True)
    first = pilot.start(tender_id)
    second = pilot.start(tender_id, offset=first.next_offset)
    client.complete_all()
    client.jobs[first.receipts[0].job_id]["status"] = terminal
    with pytest.raises(DataPlatformError):
        pilot.require_ready(tender_id, [first, second])


def test_partial_jobs_changed_revision_and_bad_completions_fail_closed() -> None:
    repo, tender_id = seeded_repo(9)
    client = FakeClient()
    pilot = TwoModeTenderIndexer(repo, client, async_enabled=True)
    first = pilot.start(tender_id)
    second = pilot.start(tender_id, offset=first.next_offset)
    client.complete_all()
    bad_id = first.receipts[0].job_id
    client.jobs[bad_id]["result"] = {"chunks": 1}
    with pytest.raises(DataPlatformError, match="committed"):
        pilot.require_ready(tender_id, [first, second])
    client.complete_all()
    assert pilot.require_ready(tender_id, [first, second])
    with pytest.raises(AsyncTenderIndexPending):
        pilot.require_ready(tender_id, [first, first, second])
    with pytest.raises(AsyncTenderIndexPending):
        pilot.require_ready(tender_id, [replace(first, expected_chunks=10), second])
    with pytest.raises(AsyncTenderIndexPending):
        pilot.require_ready(tender_id, [first])


def test_feature_off_and_small_cohorts_never_invoke_async_sdk() -> None:
    repo, tender_id = seeded_repo(3)
    client = FakeClient()
    pilot = TwoModeTenderIndexer(repo, client, async_enabled=True)
    assert pilot.mode(tender_id) == "synchronous"
    assert pilot.start(tender_id).chunks_indexed == 3
    assert client.queued == []


def test_old_sdk_missing_async_method_blocks_opt_in_without_side_effects() -> None:
    repo, tender_id = seeded_repo(9)

    class OldSDK:
        def ensure_collection(self, **kwargs):
            raise AssertionError("no writes allowed with old SDK")

    pilot = TwoModeTenderIndexer(repo, OldSDK(), async_enabled=True)
    with pytest.raises(DataPlatformError, match="updated"):
        pilot.start(tender_id)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"batch_size": 0},
        {"batch_size": 9},
        {"minimum_async_chunks": 1},
        {"minimum_async_chunks": 1001},
    ],
)
def test_config_is_bounded(kwargs: dict) -> None:
    repo, _ = seeded_repo(9)
    with pytest.raises(ValueError):
        TwoModeTenderIndexer(repo, FakeClient(), **kwargs)
