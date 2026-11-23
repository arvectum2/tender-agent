"""Persistent Tender Agent controller for opt-in Data Platform background ingest.

Receipts survive Tender Agent crashes; source identity is revision+chunk+hash.
This module never starts the shared Qwen, a scheduler or a DP worker.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.shared.data_platform import DataPlatformError, DataPlatformHttpClient
from src.tender_research.models import TenderAsyncIndexReceipt
from src.tender_research.rag.data_platform import build_tender_collection_id
from src.tender_research.rag.two_mode_ingest import (
    AsyncTenderIndexPending,
    TwoModeTenderIndexer,
)
from src.tender_research.repository import TenderRepository

_TERMINAL_BAD = frozenset({"cancelled", "dead_letter"})


@dataclass(frozen=True)
class TenderAsyncIndexProgress:
    tender_id: str
    collection_id: str
    expected: int
    submitted: int
    completed: int
    running: int
    failed: int
    next_offset: int | None
    ready: bool


class DurableTenderAsyncIndex:
    """Drive one bounded wave per call; persist each committed queue receipt.

    Caller repeats advance() as DP work finishes. poll() refreshes durable
    state without adding new jobs. require_ready() protects every retrieval
    entrypoint while the opt-in background mode is enabled.
    """

    def __init__(
        self,
        repo: TenderRepository,
        client: DataPlatformHttpClient,
        *,
        minimum_async_chunks: int = 9,
        batch_size: int = 8,
    ) -> None:
        self.repo = repo
        self.client = client
        self.bridge = TwoModeTenderIndexer(
            repo,
            client,
            async_enabled=True,
            minimum_async_chunks=minimum_async_chunks,
            batch_size=batch_size,
        )

    def _scope(self, tender_id: str):
        chunks = self.repo.list_chunks_by_tender(tender_id)
        collection = build_tender_collection_id(self.repo, tender_id)
        if collection is None or not chunks:
            raise AsyncTenderIndexPending("Tender has no indexed source revision")
        return chunks, collection

    def _rows(
        self, tender_id: str, collection_id: str
    ) -> list[TenderAsyncIndexReceipt]:
        session = self.repo._session
        return list(
            session.scalars(
                select(TenderAsyncIndexReceipt).where(
                    TenderAsyncIndexReceipt.tender_id == tender_id,
                    TenderAsyncIndexReceipt.collection_id == collection_id,
                )
            )
        )

    @staticmethod
    def _sha(chunk) -> str:
        return hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()

    def _validate_existing(
        self,
        chunks: list,
        rows: list[TenderAsyncIndexReceipt],
    ) -> list[TenderAsyncIndexReceipt]:
        if len(rows) > len(chunks):
            raise DataPlatformError(
                "Background receipt surplus for current source revision"
            )
        by_id = {row.chunk_id: row for row in rows}
        if len(by_id) != len(rows):
            raise DataPlatformError("Duplicate background source receipts")
        for chunk in chunks:
            row = by_id.get(chunk.id)
            if row is not None and (
                row.source_sha256 != self._sha(chunk)
                or row.expected_chunks != len(chunks)
            ):
                raise DataPlatformError("Background receipt source revision changed")
        known = {chunk.id for chunk in chunks}
        if not set(by_id).issubset(known):
            raise DataPlatformError("Background receipt refers to a removed chunk")
        prefix = [by_id[chunk.id] for chunk in chunks[: len(rows)] if chunk.id in by_id]
        if len(prefix) != len(rows):
            raise AsyncTenderIndexPending(
                "Background submissions are not a contiguous source prefix"
            )
        return prefix

    def _store_receipt(
        self, tender_id: str, chunk, collection_id: str, job_id: str, status: str
    ):
        session = self.repo._session
        record = TenderAsyncIndexReceipt(
            tender_id=tender_id,
            collection_id=collection_id,
            chunk_id=chunk.id,
            source_sha256=self._sha(chunk),
            expected_chunks=len(self.repo.list_chunks_by_tender(tender_id)),
            job_id=job_id,
            status=status,
        )
        # Commit separately: after a process crash, replay with the same
        # source-specific Idempotency-Key returns this exact remote job.
        try:
            with session.begin_nested():
                session.add(record)
                session.flush()
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.scalar(
                select(TenderAsyncIndexReceipt).where(
                    TenderAsyncIndexReceipt.tender_id == tender_id,
                    TenderAsyncIndexReceipt.collection_id == collection_id,
                    TenderAsyncIndexReceipt.chunk_id == chunk.id,
                )
            )
            if (
                existing is None
                or existing.job_id != job_id
                or existing.source_sha256 != self._sha(chunk)
                or existing.expected_chunks
                != len(self.repo.list_chunks_by_tender(tender_id))
            ):
                raise DataPlatformError(
                    "Concurrent background enqueue conflict"
                ) from None

    def poll(self, tender_id: str) -> TenderAsyncIndexProgress:
        chunks, collection_id = self._scope(tender_id)
        rows = self._validate_existing(chunks, self._rows(tender_id, collection_id))
        getter = getattr(self.client, "get_ingest_job", None)
        if not callable(getter):
            raise DataPlatformError(
                "Updated Data Platform SDK required for background job polling"
            )
        for row in rows:
            if row.status in _TERMINAL_BAD:
                continue
            if (
                row.status == "completed"
                and row.resource_id
                and row.document_id
                and row.indexed_chunks
            ):
                continue
            receipt = self.bridge._validate_receipt(
                getter(collection_id=collection_id, job_id=row.job_id),
                collection_id,
            )
            if receipt["job_id"] != row.job_id:
                raise DataPlatformError("Background job identity mismatch")
            if receipt["status"] == "completed":
                result = receipt.get("result")
                if (
                    not isinstance(result, dict)
                    or not result.get("resource_id")
                    or not result.get("document_id")
                    or type(result.get("chunks")) is not int
                    or result["chunks"] != 1
                ):
                    raise DataPlatformError(
                        "Background completion has no indexed evidence"
                    )
                row.resource_id = str(result["resource_id"])
                row.document_id = str(result["document_id"])
                row.indexed_chunks = result["chunks"]
            row.status = receipt["status"]
        if rows:
            self.repo._session.commit()
        total = len(chunks)
        complete = sum(
            row.status == "completed"
            and row.resource_id is not None
            and row.document_id is not None
            and row.indexed_chunks is not None
            and row.indexed_chunks == 1
            for row in rows
        )
        running = sum(row.status in {"queued", "running"} for row in rows)
        failed = sum(row.status in _TERMINAL_BAD for row in rows)
        return TenderAsyncIndexProgress(
            tender_id=tender_id,
            collection_id=collection_id,
            expected=total,
            submitted=len(rows),
            completed=complete,
            running=running,
            failed=failed,
            next_offset=len(rows) if len(rows) < total else None,
            ready=complete == total and failed == 0 and len(rows) == total,
        )

    def advance(self, tender_id: str) -> TenderAsyncIndexProgress:
        chunks, collection_id = self._scope(tender_id)
        progress = self.poll(tender_id)
        if progress.failed:
            raise DataPlatformError("Background tender index has failed jobs")
        if progress.ready or progress.running:
            return progress
        if progress.next_offset is None:
            return progress
        batch = self.bridge.start(tender_id, offset=progress.next_offset)
        for receipt in batch.receipts:
            chunk = next(chunk for chunk in chunks if chunk.id == receipt.chunk_id)
            self._store_receipt(
                tender_id,
                chunk,
                collection_id,
                receipt.job_id,
                receipt.status,
            )
        return self.poll(tender_id)

    def require_ready(self, tender_id: str) -> str:
        progress = self.poll(tender_id)
        if progress.failed:
            raise DataPlatformError("Background tender index failed")
        if not progress.ready:
            raise AsyncTenderIndexPending(
                f"Tender background index not complete: {progress.completed}/{progress.expected}"
            )
        from src.tender_research.rag.data_platform import complete_index_counts

        if not complete_index_counts(
            self.client.collection_stats(progress.collection_id), progress.expected
        ):
            raise AsyncTenderIndexPending(
                "Background collection counts are not fully indexed"
            )
        return progress.collection_id


def require_existing_background_ready(
    repo: TenderRepository,
    tender_id: str,
    *,
    enabled: bool | None = None,
    minimum_async_chunks: int | None = None,
) -> None:
    """Read-only gate for active retrieval paths: no network, no status mutation.

    An empty receipt table is blocked only when opt-in async mode is active
    for a large tender; previously indexed synchronous collections remain
    available when the feature is disabled.
    """
    from src.tender_research.config import load_config

    if enabled is None or minimum_async_chunks is None:
        config = load_config()
        if enabled is None:
            enabled = config.rag_async_ingest_enabled
        if minimum_async_chunks is None:
            minimum_async_chunks = config.rag_async_ingest_min_chunks
    if not enabled:
        return
    chunks = repo.list_chunks_by_tender(tender_id)
    if len(chunks) < minimum_async_chunks:
        return
    collection_id = build_tender_collection_id(repo, tender_id)
    if not collection_id:
        raise AsyncTenderIndexPending("Tender collection revision missing")
    rows = list(
        repo._session.scalars(
            select(TenderAsyncIndexReceipt).where(
                TenderAsyncIndexReceipt.tender_id == tender_id,
                TenderAsyncIndexReceipt.collection_id == collection_id,
            )
        )
    )
    if len(rows) != len(chunks):
        raise AsyncTenderIndexPending("Pending background tender indexing")
    hashes = {
        chunk.id: hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
        for chunk in chunks
    }
    if len({r.resource_id for r in rows}) != len(rows) or len(
        {r.document_id for r in rows}
    ) != len(rows):
        raise AsyncTenderIndexPending("Background indexed identities are not unique")
    if {r.chunk_id for r in rows} != set(hashes) or any(
        r.source_sha256 != hashes[r.chunk_id]
        or r.expected_chunks != len(chunks)
        or r.status != "completed"
        or not r.resource_id
        or not r.document_id
        or r.indexed_chunks is None
        or r.indexed_chunks != 1
        for r in rows
    ):
        raise AsyncTenderIndexPending("Background indexing not verified")
