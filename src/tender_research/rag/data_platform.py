from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from src.shared.data_platform import DataPlatformError, DataPlatformHttpClient
from src.tender_research.providers.ri223_rar_members import is_ri223_rar_document
from src.tender_research.rag.presets import (
    TENDER_SEARCH_PROFILE,
    legacy_tender_collection_id,
    tender_collection_id,
    tender_processing_collection_id,
    tender_recovery_processing_collection_id,
)
from src.tender_research.rag.search_types import RagSearchHit
from src.tender_research.repository import TenderRepository

_CHUNK_URI_PREFIX = "tender-chunk://"
_OCR_REVIEW_CONFIDENCE_THRESHOLD = 90.0


def _processing_metadata(payload: dict) -> dict | None:
    value = payload.get("metadata")
    return dict(value) if isinstance(value, dict) else None


def _ocr_review_projection(metadata: dict | None) -> dict:
    if metadata is None:
        return {
            "ocr_used": None,
            "requires_review": True,
            "reason": "processing_metadata_unavailable",
            "provider": None,
            "mean_confidence": None,
            "review_below_confidence": _OCR_REVIEW_CONFIDENCE_THRESHOLD,
        }

    ocr = metadata.get("ocr")
    if not isinstance(ocr, dict):
        return {
            "ocr_used": False,
            "requires_review": False,
            "reason": "ocr_not_used",
            "provider": None,
            "mean_confidence": None,
            "review_below_confidence": _OCR_REVIEW_CONFIDENCE_THRESHOLD,
        }

    provider = str(ocr.get("provider") or "").strip() or None
    raw_pages = ocr.get("page_numbers")
    page_numbers = list(raw_pages) if isinstance(raw_pages, (list, tuple)) else []
    ocr_used = bool(provider or page_numbers)
    if not ocr_used:
        return {
            "ocr_used": False,
            "requires_review": False,
            "reason": "ocr_not_used",
            "provider": provider,
            "mean_confidence": None,
            "review_below_confidence": _OCR_REVIEW_CONFIDENCE_THRESHOLD,
        }

    raw_confidence = ocr.get("mean_confidence")
    confidence = (
        float(raw_confidence)
        if isinstance(raw_confidence, (int, float)) and not isinstance(raw_confidence, bool)
        else None
    )
    if confidence is None:
        return {
            "ocr_used": True,
            "requires_review": True,
            "reason": "ocr_confidence_missing",
            "provider": provider,
            "mean_confidence": None,
            "review_below_confidence": _OCR_REVIEW_CONFIDENCE_THRESHOLD,
        }
    requires_review = confidence < _OCR_REVIEW_CONFIDENCE_THRESHOLD
    return {
        "ocr_used": True,
        "requires_review": requires_review,
        "reason": "ocr_low_confidence" if requires_review else "ocr_confidence_accepted",
        "provider": provider,
        "mean_confidence": confidence,
        "review_below_confidence": _OCR_REVIEW_CONFIDENCE_THRESHOLD,
    }


def _project_processing_evidence(document, payload: dict) -> dict:
    metadata = _processing_metadata(payload)
    review = _ocr_review_projection(metadata)
    raw_meta = dict(getattr(document, "raw_meta", None) or {})
    raw_meta["data_platform_processing"] = {
        "resource_id": payload.get("resource_id"),
        "document_id": payload.get("document_id"),
        "canonical_uri": payload.get("canonical_uri"),
        "metadata_available": metadata is not None,
        "metadata": metadata or {},
        "ocr_review": review,
    }
    document.raw_meta = raw_meta
    return review


@dataclass(frozen=True)
class DataPlatformIndexSummary:
    collection_id: str | None
    chunks_seen: int
    chunks_indexed: int
    platform_chunks_created: int
    embeddings_created: int


@dataclass(frozen=True)
class DataPlatformProjectionSummary:
    documents_seen: int
    documents_processed: int
    documents_skipped_existing: int
    documents_failed: int
    extracted_documents: int
    chunks_projected: int
    chunks_pruned: int


def _processing_collection_id(tender_id: str) -> str:
    return tender_processing_collection_id(str(tender_id))


def _document_uri(document_id: str) -> str:
    return f"tender-document://{document_id}"


def _tender_collection_revision(
    repo: TenderRepository,
    tender_id: str,
) -> str | None:
    chunks = repo.list_chunks_by_tender(tender_id)
    if not chunks:
        return None
    payload = "\n".join(
        f"{chunk.id}:{chunk.text_hash}"
        for chunk in sorted(chunks, key=lambda item: item.id)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_tender_collection_id(
    repo: TenderRepository,
    tender_id: str,
) -> str | None:
    revision = _tender_collection_revision(repo, tender_id)
    if revision is None:
        return None
    return tender_collection_id(str(tender_id), revision)


def build_legacy_tender_collection_id(
    repo: TenderRepository,
    tender_id: str,
) -> str | None:
    revision = _tender_collection_revision(repo, tender_id)
    if revision is None:
        return None
    return legacy_tender_collection_id(str(tender_id), revision)


def resolve_tender_collection_id(
    repo: TenderRepository,
    client: DataPlatformHttpClient,
    tender_id: str,
) -> str | None:
    canonical = build_tender_collection_id(repo, tender_id)
    if canonical is None:
        return None
    if client.collection_exists(canonical):
        return canonical
    legacy = build_legacy_tender_collection_id(repo, tender_id)
    if legacy is not None and client.collection_exists(legacy):
        return legacy
    return None


def _chunk_uri(chunk_id: str) -> str:
    return f"{_CHUNK_URI_PREFIX}{chunk_id}"


def _chunk_id_from_uri(uri: str) -> str | None:
    if not uri.startswith(_CHUNK_URI_PREFIX):
        return None
    value = uri[len(_CHUNK_URI_PREFIX) :].strip()
    return value or None


def retrieval_backend_name(config) -> str:
    backend = str(
        getattr(config, "rag_retrieval_backend", "data_platform") or "data_platform"
    ).strip().lower()
    if backend != "data_platform":
        raise ValueError(
            "rag_retrieval_backend must be 'data_platform'; "
            "the legacy local RAG backend has been removed"
        )
    return backend


def build_data_platform_client(config) -> DataPlatformClient:
    return DataPlatformClient(
        base_url=config.rag_data_platform_base_url,
        api_key=config.rag_data_platform_api_key,
        timeout_seconds=config.rag_data_platform_timeout_seconds,
    )


class DataPlatformClient(DataPlatformHttpClient):
    def ensure_collection(
        self,
        *,
        collection_id: str,
        name: str,
        owner: str = "tender-agent",
    ) -> dict:
        return super().ensure_collection(
            collection_id=collection_id,
            name=name,
            owner=owner,
        )

    def ingest_chunk(
        self,
        *,
        collection_id: str,
        chunk_id: str,
        file_name: str,
        text: str,
    ) -> dict:
        return self.ingest_document(
            collection_id=collection_id,
            canonical_uri=_chunk_uri(chunk_id),
            title=file_name,
            text=text,
            filename=f"{chunk_id}.txt",
            pre_chunked=True,
        )


class DataPlatformDocumentProjector:
    """Project platform-owned extraction/chunking into Tender Agent domain storage.

    Data Platform remains authoritative for generic document processing. Tender
    Agent stores only a compatibility/domain projection so procurement evidence,
    Decision Core and report code can keep stable local references during the
    migration away from the legacy local RAG stack.
    """

    def __init__(
        self,
        repo: TenderRepository,
        client: DataPlatformClient,
        config,
    ) -> None:
        self._repo = repo
        self._client = client
        self._config = config

    def build_for_tender(
        self,
        tender,
        *,
        rebuild: bool = False,
    ) -> DataPlatformProjectionSummary:
        seen = processed = skipped = failed = extracted = projected = pruned = 0
        for document in list(tender.documents):
            # Source-bound RAR is an opaque container; only verified inner documents
            # are eligible for Data Platform text/OCR/chunk extraction.
            if is_ri223_rar_document(document):
                skipped += 1
                continue
            if document.download_status != "downloaded":
                continue
            seen += 1
            existing_chunks = self._repo.list_document_chunks(document.id)
            projected_chunks = [
                chunk
                for chunk in existing_chunks
                if isinstance(chunk.raw_meta, dict)
                and chunk.raw_meta.get("source") == "data_platform_projection"
            ]
            if (
                not rebuild
                and document.text_extraction_status == "extracted"
                and document.extracted_text_path
                and existing_chunks
                and len(projected_chunks) == len(existing_chunks)
            ):
                skipped += 1
                continue
            if not document.local_path:
                failed += 1
                continue
            local_path = Path(document.local_path)
            if not local_path.is_file():
                failed += 1
                continue

            try:
                payload = self._client.process_document(
                    collection_id=_processing_collection_id(str(tender.id)),
                    canonical_uri=_document_uri(str(document.id)),
                    title=document.file_name or str(document.id),
                    content=local_path.read_bytes(),
                    filename=document.file_name or local_path.name,
                    content_type=document.content_type or "application/octet-stream",
                    chunk_size_chars=self._config.rag_chunk_size_chars,
                    overlap_chars=self._config.rag_chunk_overlap_chars,
                    min_chunk_chars=self._config.rag_min_chunk_chars,
                    max_chars=self._config.document_extract_max_chars,
                )
            except (DataPlatformError, OSError, ValueError):
                meta = document.raw_meta if isinstance(document.raw_meta, dict) else {}
                if meta.get("source") != "RI223_RAR_MEMBER":
                    raise
                document.text_extraction_status = "failed"
                document.extracted_text_path = None
                document.extracted_text_chars = 0
                document.raw_meta = {
                    **meta,
                    "text_projection": {
                        "status": "NEEDS_REVIEW",
                        "reason": "Data Platform processing failed",
                    },
                }
                failed += 1
                continue
            processed += 1
            _project_processing_evidence(document, payload)
            status = str(payload.get("extraction_status") or "failed")
            text = str(payload.get("text") or "")
            document.text_extraction_status = status
            if status == "extracted" and text:
                text_dir = local_path.parent.parent / "extracted_text"
                text_dir.mkdir(parents=True, exist_ok=True)
                text_path = text_dir / f"{document.id}.txt"
                text_path.write_text(text, encoding="utf-8")
                document.extracted_text_path = str(text_path)
                document.extracted_text_chars = len(text)
                extracted += 1
            else:
                document.extracted_text_path = None
                document.extracted_text_chars = 0

            keep_ids: set[str] = set()
            raw_chunks = payload.get("chunks")
            if not isinstance(raw_chunks, list):
                raw_chunks = []
            for item in raw_chunks:
                if not isinstance(item, dict):
                    continue
                chunk_text = str(item.get("text") or "")
                content_hash = str(item.get("content_hash") or "")
                if not chunk_text or not content_hash:
                    continue
                chunk = self._repo.upsert_document_chunk(
                    {
                        "tender_id": document.tender_id,
                        "document_id": document.id,
                        "chunk_index": int(item.get("ordinal", 0)),
                        "text": chunk_text,
                        "text_hash": content_hash,
                        "char_start": int(item.get("char_start", 0)),
                        "char_end": int(item.get("char_end", 0)),
                        "token_estimate": int(item.get("token_estimate", 0)),
                        "source_file_name": document.file_name,
                        "source_text_path": document.extracted_text_path,
                        "raw_meta": {
                            "source": "data_platform_projection",
                            "data_platform": {
                                "resource_id": payload.get("resource_id"),
                                "document_id": payload.get("document_id"),
                                "chunk_id": item.get("chunk_id"),
                                "canonical_uri": payload.get("canonical_uri"),
                                "content_hash": item.get("content_hash"),
                            },
                        },
                    }
                )
                keep_ids.add(chunk.id)
                projected += 1
            pruned += self._repo.prune_document_chunks(
                document.id,
                keep_chunk_ids=keep_ids,
            )
        for parent in list(tender.documents):
            if not is_ri223_rar_document(parent):
                continue
            meta = parent.raw_meta if isinstance(parent.raw_meta, dict) else {}
            state = meta.get("rar_analysis")
            if not isinstance(state, dict) or state.get("status") not in {
                "CHILDREN_REGISTERED", "TEXT_READY_FOR_ANALYSIS", "NEEDS_REVIEW",
            }:
                continue
            children = [
                doc for doc in tender.documents
                if isinstance(doc.raw_meta, dict)
                and doc.raw_meta.get("source") == "RI223_RAR_MEMBER"
                and doc.raw_meta.get("parent_document_id") == parent.id
            ]
            expected = int(state.get("member_count") or 0)
            if expected <= 0 or not children:
                continue
            extracted_children = sum(
                doc.text_extraction_status == "extracted"
                and bool(doc.extracted_text_path)
                for doc in children
            )
            complete = len(children) == expected and extracted_children == expected
            parent.raw_meta = {
                **meta,
                "rar_analysis": {
                    **state,
                    "status": "TEXT_READY_FOR_ANALYSIS" if complete else "NEEDS_REVIEW",
                    "text_projection_complete": complete,
                    "members_registered": len(children),
                    "members_text_extracted": extracted_children,
                    # Domain-specific GO / NO_GO analysis is separate from text extraction.
                    "content_analysis_complete": False,
                },
            }
        self._repo._session.commit()
        return DataPlatformProjectionSummary(
            documents_seen=seen,
            documents_processed=processed,
            documents_skipped_existing=skipped,
            documents_failed=failed,
            extracted_documents=extracted,
            chunks_projected=projected,
            chunks_pruned=pruned,
        )


def extract_document_with_data_platform(
    document,
    output_dir: Path,
    config,
    *,
    client_factory=None,
) -> None:
    """Populate the legacy extraction-shaped object through Data Platform."""

    source_path = Path(document.local_path or "")
    if not source_path.is_file():
        raise DataPlatformError(
            f"recovery document {document.id} source file is unavailable"
        )
    factory = client_factory or build_data_platform_client
    with factory(config) as client:
        payload = client.process_document(
            collection_id=tender_recovery_processing_collection_id(),
            canonical_uri=_document_uri(str(document.id)),
            title=document.file_name or str(document.id),
            content=source_path.read_bytes(),
            filename=document.file_name or source_path.name,
            content_type="application/octet-stream",
            chunk_size_chars=config.rag_chunk_size_chars,
            overlap_chars=config.rag_chunk_overlap_chars,
            min_chunk_chars=config.rag_min_chunk_chars,
            max_chars=config.document_extract_max_chars,
        )
    _project_processing_evidence(document, payload)
    status = str(payload.get("extraction_status") or "failed")
    text = str(payload.get("text") or "")
    document.text_extraction_status = status
    document.extracted_text_chars = len(text) if status == "extracted" else 0
    document.extracted_text_path = None
    if status == "extracted" and text:
        output_dir.mkdir(parents=True, exist_ok=True)
        text_path = output_dir / f"{document.id}.txt"
        text_path.write_text(text, encoding="utf-8")
        document.extracted_text_path = str(text_path)


class DataPlatformRecoveryChunkIndexer:
    """Build recovery chunks through Data Platform without local chunking.

    Recovery already validates and publishes the authoritative source and
    extracted-text files. This adapter sends the source document through the
    platform-owned processing boundary, requires the extracted text to match
    byte-for-byte, and projects only the returned chunks into procurement
    storage.
    """

    def __init__(
        self,
        repo: TenderRepository,
        config,
        *,
        client_factory=None,
    ) -> None:
        self._repo = repo
        self._config = config
        self._client_factory = client_factory or build_data_platform_client

    def build_for_tender(self, tender_id: str, *, commit: bool = True) -> dict:
        documents = self._repo.list_extracted_documents_by_tender(tender_id)
        summary = {
            "documents_seen": 0,
            "documents_processed": 0,
            "chunks_created": 0,
            "chunks_skipped_existing": 0,
            "chunks_pruned": 0,
        }
        with self._client_factory(self._config) as client:
            for document in documents:
                summary["documents_seen"] += 1
                source_path = Path(document.local_path or "")
                text_path = Path(document.extracted_text_path or "")
                if not source_path.is_file() or not text_path.is_file():
                    raise DataPlatformError(
                        f"recovery document {document.id} is missing source or extracted text"
                    )
                expected_text = text_path.read_text(encoding="utf-8")
                payload = client.process_document(
                    collection_id=_processing_collection_id(str(tender_id)),
                    canonical_uri=_document_uri(str(document.id)),
                    title=document.file_name or str(document.id),
                    content=source_path.read_bytes(),
                    filename=document.file_name or source_path.name,
                    content_type=document.content_type or "application/octet-stream",
                    chunk_size_chars=self._config.rag_chunk_size_chars,
                    overlap_chars=self._config.rag_chunk_overlap_chars,
                    min_chunk_chars=self._config.rag_min_chunk_chars,
                    max_chars=self._config.document_extract_max_chars,
                )
                _project_processing_evidence(document, payload)
                if (
                    str(payload.get("extraction_status") or "") != "extracted"
                    or str(payload.get("text") or "") != expected_text
                ):
                    raise DataPlatformError(
                        f"Data Platform extraction mismatch for recovery document {document.id}"
                    )

                existing_chunks = self._repo.list_document_chunks(document.id)
                existing_by_index = {
                    chunk.chunk_index: chunk for chunk in existing_chunks
                }
                existing_by_hash = {
                    chunk.text_hash: chunk for chunk in existing_chunks
                }
                keep_ids: set[str] = set()
                raw_chunks = payload.get("chunks")
                if not isinstance(raw_chunks, list):
                    raise DataPlatformError(
                        f"Data Platform returned invalid chunks for recovery document {document.id}"
                    )
                for item in raw_chunks:
                    if not isinstance(item, dict):
                        raise DataPlatformError(
                            f"Data Platform returned invalid chunk for recovery document {document.id}"
                        )
                    chunk_text = str(item.get("text") or "")
                    content_hash = str(item.get("content_hash") or "")
                    if not chunk_text or not content_hash:
                        raise DataPlatformError(
                            f"Data Platform returned empty chunk for recovery document {document.id}"
                        )
                    chunk_index = int(item.get("ordinal", 0))
                    existing = existing_by_index.get(chunk_index)
                    if existing is None:
                        existing = existing_by_hash.get(content_hash)
                    chunk = self._repo.upsert_document_chunk(
                        {
                            "tender_id": document.tender_id,
                            "document_id": document.id,
                            "chunk_index": chunk_index,
                            "text": chunk_text,
                            "text_hash": content_hash,
                            "char_start": int(item.get("char_start", 0)),
                            "char_end": int(item.get("char_end", 0)),
                            "token_estimate": int(item.get("token_estimate", 0)),
                            "source_file_name": document.file_name,
                            "source_text_path": document.extracted_text_path,
                            "raw_meta": {
                                "source": "data_platform_recovery_projection",
                                "data_platform": {
                                    "resource_id": payload.get("resource_id"),
                                    "document_id": payload.get("document_id"),
                                    "chunk_id": item.get("chunk_id"),
                                    "canonical_uri": payload.get("canonical_uri"),
                                    "content_hash": content_hash,
                                },
                            },
                        }
                    )
                    keep_ids.add(chunk.id)
                    if existing is None:
                        summary["chunks_created"] += 1
                    else:
                        summary["chunks_skipped_existing"] += 1
                summary["chunks_pruned"] += self._repo.prune_document_chunks(
                    document.id,
                    keep_chunk_ids=keep_ids,
                )
                summary["documents_processed"] += 1
        if commit:
            self._repo._session.commit()
        else:
            self._repo._session.flush()
        return summary


def build_recovery_chunk_indexer(
    repo: TenderRepository,
    config,
) -> DataPlatformRecoveryChunkIndexer:
    return DataPlatformRecoveryChunkIndexer(repo, config)


class DataPlatformTenderIndexer:
    def __init__(
        self,
        repo: TenderRepository,
        client: DataPlatformClient,
    ) -> None:
        self._repo = repo
        self._client = client

    def build_for_tender(self, tender_id: str) -> DataPlatformIndexSummary:
        chunks = self._repo.list_chunks_by_tender(tender_id)
        collection_id = build_tender_collection_id(self._repo, tender_id)
        if not chunks or collection_id is None:
            return DataPlatformIndexSummary(
                collection_id=None,
                chunks_seen=0,
                chunks_indexed=0,
                platform_chunks_created=0,
                embeddings_created=0,
            )

        tender = self._repo.get_tender_by_id(tender_id)
        if tender is None:
            raise DataPlatformError(f"Tender {tender_id} disappeared during indexing")

        self._client.ensure_collection(
            collection_id=collection_id,
            name=f"Tender {tender.registry_number or tender.id}",
        )

        indexed = 0
        platform_chunks = 0
        embeddings = 0
        for chunk in chunks:
            result = self._client.ingest_chunk(
                collection_id=collection_id,
                chunk_id=chunk.id,
                file_name=chunk.source_file_name or f"{chunk.document_id}.txt",
                text=chunk.text,
            )
            indexed += 1
            platform_chunks += int(result.get("chunks", 0) or 0)
            embeddings += int(result.get("embeddings", 0) or 0)

        return DataPlatformIndexSummary(
            collection_id=collection_id,
            chunks_seen=len(chunks),
            chunks_indexed=indexed,
            platform_chunks_created=platform_chunks,
            embeddings_created=embeddings,
        )


class DataPlatformRagRetriever:
    def __init__(
        self,
        repo: TenderRepository,
        client: DataPlatformClient,
    ) -> None:
        self._repo = repo
        self._client = client

    def close(self) -> None:
        self._client.close()

    def search_documents(
        self,
        query: str,
        *,
        tender_id: str | None = None,
        registry_number: str | None = None,
        customer_name: str | None = None,
        limit: int = 10,
    ) -> list[RagSearchHit]:
        if not query.strip():
            return []
        tender = None
        if tender_id:
            tender = self._repo.get_tender_by_id(tender_id)
        elif registry_number:
            tender = self._repo.get_tender_by_registry_number(registry_number)
            tender_id = str(tender.id) if tender else None
        if tender_id is None or tender is None:
            return []
        if registry_number and tender.registry_number != registry_number:
            return []
        if customer_name:
            actual = (tender.customer_name or "").casefold()
            if customer_name.casefold() not in actual:
                return []

        collection_id = resolve_tender_collection_id(
            self._repo, self._client, tender_id
        )
        if collection_id is None:
            return []
        return self._search(query, [collection_id], limit=limit)

    def search_all_documents(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[RagSearchHit]:
        if not query.strip():
            return []
        collections = [
            collection_id
            for tender_id in self._repo.list_tender_ids_with_chunks()
            if (
                collection_id := resolve_tender_collection_id(
                    self._repo, self._client, tender_id
                )
            )
            is not None
        ]
        if not collections:
            return []
        return self._search(query, collections, limit=limit)

    def _search(
        self,
        query: str,
        collections: list[str],
        *,
        limit: int,
    ) -> list[RagSearchHit]:
        raw_hits = self._client.search_with_profile(
            query=query,
            collections=collections,
            limit=max(limit * 2, limit),
            profile=TENDER_SEARCH_PROFILE,
        )
        result: list[RagSearchHit] = []
        seen_chunk_ids: set[str] = set()
        for raw in raw_hits:
            chunk_id = _chunk_id_from_uri(str(raw.get("canonical_uri") or ""))
            if not chunk_id or chunk_id in seen_chunk_ids:
                continue
            context = self._repo.get_chunk_context(chunk_id)
            if context is None:
                continue
            scores = raw.get("scores")
            score = (
                float(scores.get("fusion", 0.0))
                if isinstance(scores, dict)
                else 0.0
            )
            seen_chunk_ids.add(chunk_id)
            result.append(
                RagSearchHit(
                    chunk_id=context["chunk_id"],
                    score=score,
                    registry_number=context["registry_number"],
                    tender_id=context["tender_id"],
                    tender_title=context["tender_title"],
                    customer_name=context["customer_name"],
                    document_id=context["document_id"],
                    file_name=context["file_name"],
                    chunk_index=context["chunk_index"],
                    preview=context["text"][:280].replace("\n", " ").strip(),
                    text=context["text"],
                )
            )
            if len(result) >= limit:
                break
        return result
