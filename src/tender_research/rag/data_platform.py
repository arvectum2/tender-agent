from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Self

import httpx

from src.tender_research.rag.retriever import RagSearchHit
from src.tender_research.repository import TenderRepository

_COLLECTION_PREFIX = "tender-agent"
_CHUNK_URI_PREFIX = "tender-chunk://"

# Procurement retrieval is semantic-first. Equal-weight RRF can over-promote
# a weak lexical singleton that is only a deep semantic candidate.
_TENDER_LEXICAL_WEIGHT = 1.0
_TENDER_VECTOR_WEIGHT = 4.0


class DataPlatformError(RuntimeError):
    pass


@dataclass(frozen=True)
class DataPlatformIndexSummary:
    collection_id: str | None
    chunks_seen: int
    chunks_indexed: int
    platform_chunks_created: int
    embeddings_created: int


def build_tender_collection_id(
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
    revision = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{_COLLECTION_PREFIX}:{tender_id}:{revision}"


def _chunk_uri(chunk_id: str) -> str:
    return f"{_CHUNK_URI_PREFIX}{chunk_id}"


def _chunk_id_from_uri(uri: str) -> str | None:
    if not uri.startswith(_CHUNK_URI_PREFIX):
        return None
    value = uri[len(_CHUNK_URI_PREFIX) :].strip()
    return value or None


def retrieval_backend_name(config) -> str:
    backend = str(getattr(config, "rag_retrieval_backend", "legacy") or "legacy").strip().lower()
    if backend not in {"legacy", "data_platform"}:
        raise ValueError(
            "rag_retrieval_backend must be either 'legacy' or 'data_platform'"
        )
    return backend


def build_data_platform_client(config) -> DataPlatformClient:
    return DataPlatformClient(
        base_url=config.rag_data_platform_base_url,
        api_key=config.rag_data_platform_api_key,
        timeout_seconds=config.rag_data_platform_timeout_seconds,
    )


class DataPlatformClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        timeout_seconds: int = 30,
        client: httpx.Client | None = None,
    ) -> None:
        normalized = base_url.rstrip("/")
        if not normalized:
            raise ValueError("Data Platform base URL must not be blank")
        headers = {"X-Arvectum-Key": api_key} if api_key else {}
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=normalized,
            timeout=timeout_seconds,
            headers=headers,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise DataPlatformError(f"Data Platform request failed: {exc}") from exc
        if response.status_code >= 400:
            detail = response.text.strip()[:500]
            raise DataPlatformError(
                f"Data Platform {method} {path} returned HTTP "
                f"{response.status_code}: {detail}"
            )
        return response

    def ensure_collection(
        self,
        *,
        collection_id: str,
        name: str,
        owner: str = "tender-agent",
    ) -> dict[str, Any]:
        try:
            response = self._client.get(f"/v1/collections/{collection_id}")
        except httpx.HTTPError as exc:
            raise DataPlatformError(
                f"Data Platform collection lookup failed: {exc}"
            ) from exc
        if response.status_code == 200:
            return response.json()
        if response.status_code != 404:
            detail = response.text.strip()[:500]
            raise DataPlatformError(
                "Data Platform collection lookup failed with HTTP "
                f"{response.status_code}: {detail}"
            )
        return self._request(
            "POST",
            "/v1/collections",
            json={
                "collection_id": collection_id,
                "owner": owner,
                "name": name,
                "default_language": "russian",
            },
        ).json()

    def ingest_chunk(
        self,
        *,
        collection_id: str,
        chunk_id: str,
        file_name: str,
        text: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/ingest/document",
            data={
                "collection_id": collection_id,
                "title": file_name,
                "canonical_uri": _chunk_uri(chunk_id),
                "pre_chunked": "true",
            },
            files={
                "file": (
                    f"{chunk_id}.txt",
                    text.encode("utf-8"),
                    "text/plain",
                )
            },
        ).json()

    def search(
        self,
        *,
        query: str,
        collections: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        payload = self._request(
            "POST",
            "/v1/search",
            json={
                "query": query,
                "collections": collections,
                "limit": limit,
                "mode": "hybrid",
                "lexical_weight": _TENDER_LEXICAL_WEIGHT,
                "vector_weight": _TENDER_VECTOR_WEIGHT,
            },
        ).json()
        hits = payload.get("hits", [])
        if not isinstance(hits, list):
            raise DataPlatformError("Data Platform search returned invalid hits payload")
        return [item for item in hits if isinstance(item, dict)]

    def collection_exists(self, collection_id: str) -> bool:
        try:
            response = self._client.get(f"/v1/collections/{collection_id}")
        except httpx.HTTPError as exc:
            raise DataPlatformError(f"Data Platform request failed: {exc}") from exc
        if response.status_code == 200:
            return True
        if response.status_code == 404:
            return False
        raise DataPlatformError(
            "Data Platform collection lookup failed with HTTP "
            f"{response.status_code}: {response.text.strip()[:500]}"
        )


    def collection_stats(self, collection_id: str) -> dict[str, int | str]:
        return self._request(
            "GET",
            f"/v1/collections/{collection_id}/stats",
        ).json()


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

        collection_id = build_tender_collection_id(self._repo, tender_id)
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
            if (collection_id := build_tender_collection_id(self._repo, tender_id))
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
        raw_hits = self._client.search(
            query=query,
            collections=collections,
            limit=max(limit * 2, limit),
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
