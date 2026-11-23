"""Opt-in Tender Agent / Data Platform two-mode ingestion boundary.

Existing synchronous Tender Agent indexing is UNCHANGED by default. The
background variant uses the same tender-chunk:// source keys and explicit
completion gating, and requires an updated shared consumer SDK.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from src.shared.data_platform import DataPlatformError, DataPlatformHttpClient
from src.tender_research.rag.data_platform import (
    DataPlatformIndexSummary,
    DataPlatformTenderIndexer,
    build_tender_collection_id,
)
from src.tender_research.repository import TenderRepository

_MINIMUM_ASYNC_CHUNKS = 9
_MAX_BATCH_JOBS = 8
_ALLOWED_STATES = {"queued", "running", "completed", "dead_letter", "cancelled"}


class AsyncTenderIndexPending(DataPlatformError):
    """One or more chunks have not yet reached searchable completion."""


@dataclass(frozen=True)
class AsyncTenderChunkReceipt:
    chunk_id: str
    collection_id: str
    job_id: str
    status: str


@dataclass(frozen=True)
class AsyncTenderIndexBatch:
    tender_id: str
    collection_id: str
    expected_chunks: int
    offset: int
    next_offset: int | None
    receipts: tuple[AsyncTenderChunkReceipt, ...]


class TwoModeTenderIndexer:
    """Small synchronous ingest or bounded opt-in background waves.

    The caller must persist returned receipts and resume at next_offset.
    No search may be exposed via search_when_ready until all known chunks
    have completed, and the source revision is unchanged.
    """

    def __init__(
        self,
        repo: TenderRepository,
        client: DataPlatformHttpClient,
        *,
        async_enabled: bool = False,
        minimum_async_chunks: int = _MINIMUM_ASYNC_CHUNKS,
        batch_size: int = _MAX_BATCH_JOBS,
    ) -> None:
        if not 2 <= minimum_async_chunks <= 1000:
            raise ValueError("minimum_async_chunks must be within 2..1000")
        if not 1 <= batch_size <= _MAX_BATCH_JOBS:
            raise ValueError("batch_size must be within 1..8")
        self._repo = repo
        self._client = client
        self._async_enabled = async_enabled
        self._minimum_async_chunks = minimum_async_chunks
        self._batch_size = batch_size

    def mode(self, tender_id: str) -> str:
        count = len(self._repo.list_chunks_by_tender(tender_id))
        return (
            "background"
            if self._async_enabled and count >= self._minimum_async_chunks
            else "synchronous"
        )

    def start(
        self, tender_id: str, *, offset: int = 0
    ) -> DataPlatformIndexSummary | AsyncTenderIndexBatch:
        if self.mode(tender_id) == "synchronous":
            if offset:
                raise ValueError("offset is valid only for background ingest")
            return DataPlatformTenderIndexer(self._repo, self._client).build_for_tender(
                tender_id
            )
        enqueue = getattr(self._client, "enqueue_ingest_document_bytes", None)
        if not callable(enqueue):
            raise DataPlatformError(
                "Opt-in background ingestion requires updated Data Platform consumer SDK"
            )
        chunks = self._repo.list_chunks_by_tender(tender_id)
        collection_id = build_tender_collection_id(self._repo, tender_id)
        tender = self._repo.get_tender_by_id(tender_id)
        if not chunks or collection_id is None or tender is None:
            raise DataPlatformError(
                "Tender or source chunks disappeared during indexing"
            )
        if offset < 0 or offset >= len(chunks):
            raise ValueError("background offset outside pending chunk range")

        self._client.ensure_collection(
            collection_id=collection_id,
            name=f"Tender {tender.registry_number or tender.id}",
            owner="tender-agent",
        )
        receipts: list[AsyncTenderChunkReceipt] = []
        for chunk in chunks[offset : offset + self._batch_size]:
            source = chunk.text.encode("utf-8")
            source_digest = hashlib.sha256(source).hexdigest()
            idem_digest = hashlib.sha256(
                f"{collection_id}\0{chunk.id}\0{source_digest}".encode()
            ).hexdigest()
            raw = enqueue(
                collection_id=collection_id,
                canonical_uri=f"tender-chunk://{chunk.id}",
                title=chunk.source_file_name or f"{chunk.document_id}.txt",
                content=source,
                filename=f"{chunk.id}.txt",
                content_type="text/plain",
                pre_chunked=True,
                idempotency_key=idem_digest,
            )
            receipt = self._validate_receipt(raw, collection_id)
            receipts.append(
                AsyncTenderChunkReceipt(
                    chunk_id=chunk.id,
                    collection_id=collection_id,
                    job_id=receipt["job_id"],
                    status=receipt["status"],
                )
            )
        end = offset + len(receipts)
        return AsyncTenderIndexBatch(
            tender_id=tender_id,
            collection_id=collection_id,
            expected_chunks=len(chunks),
            offset=offset,
            next_offset=end if end < len(chunks) else None,
            receipts=tuple(receipts),
        )

    @staticmethod
    def _validate_receipt(raw: Any, collection_id: str) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise DataPlatformError(
                "Data Platform returned invalid background job receipt"
            )
        if (
            raw.get("collection_id") != collection_id
            or not isinstance(raw.get("job_id"), str)
            or not raw["job_id"]
            or raw.get("status") not in _ALLOWED_STATES
        ):
            raise DataPlatformError(
                "Invalid collection, identity or background job state"
            )
        return raw

    def require_ready(
        self, tender_id: str, batches: list[AsyncTenderIndexBatch]
    ) -> str:
        """Fail closed on incomplete batches, failures, changed revisions or jobs."""
        getter = getattr(self._client, "get_ingest_job", None)
        if not callable(getter):
            raise DataPlatformError(
                "Opt-in background ingestion requires updated Data Platform consumer SDK"
            )
        chunks = self._repo.list_chunks_by_tender(tender_id)
        collection_id = build_tender_collection_id(self._repo, tender_id)
        if collection_id is None or not chunks:
            raise DataPlatformError("Tender source chunks are missing")
        jobs = [item for batch in batches for item in batch.receipts]
        if (
            not batches
            or any(
                batch.tender_id != tender_id
                or batch.collection_id != collection_id
                or batch.expected_chunks != len(chunks)
                for batch in batches
            )
            or len(jobs) != len(chunks)
            or {item.chunk_id for item in jobs} != {chunk.id for chunk in chunks}
            or len({item.chunk_id for item in jobs}) != len(jobs)
        ):
            raise AsyncTenderIndexPending(
                "Tender background index is incomplete or has a changed source revision"
            )
        resource_ids: set[str] = set()
        document_ids: set[str] = set()
        for item in jobs:
            receipt = self._validate_receipt(
                getter(collection_id=collection_id, job_id=item.job_id),
                collection_id,
            )
            if receipt["job_id"] != item.job_id:
                raise DataPlatformError("Background job identity changed unexpectedly")
            if receipt["status"] in {"dead_letter", "cancelled"}:
                raise DataPlatformError(
                    "Tender background index failed or was cancelled"
                )
            if receipt["status"] != "completed":
                raise AsyncTenderIndexPending(
                    "Tender background index is still processing"
                )
            result = receipt.get("result")
            if (
                not isinstance(result, dict)
                or not result.get("resource_id")
                or not result.get("document_id")
                or type(result.get("chunks")) is not int
                or result["chunks"] != 1
            ):
                raise DataPlatformError(
                    "Background completion is missing committed searchable evidence"
                )
            if (
                result["resource_id"] in resource_ids
                or result["document_id"] in document_ids
            ):
                raise DataPlatformError(
                    "Background completion duplicated source identity"
                )
            resource_ids.add(result["resource_id"])
            document_ids.add(result["document_id"])
        return collection_id

    def search_when_ready(
        self,
        tender_id: str,
        batches: list[AsyncTenderIndexBatch],
        retriever: Any,
        *,
        query: str,
        limit: int = 10,
    ) -> Any:
        self.require_ready(tender_id, batches)
        return retriever.search_documents(
            query,
            tender_id=tender_id,
            limit=limit,
        )
