from __future__ import annotations

from typing import Any, Self

import httpx


class DataPlatformError(RuntimeError):
    pass


class DataPlatformHttpClient:
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
        owner: str,
        default_language: str = "russian",
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
                "default_language": default_language,
            },
        ).json()

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
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/process/document",
            data={
                "collection_id": collection_id,
                "title": title,
                "canonical_uri": canonical_uri,
                "chunk_size_chars": str(chunk_size_chars),
                "overlap_chars": str(overlap_chars),
                "min_chunk_chars": str(min_chunk_chars),
                "max_chars": str(max_chars),
            },
            files={"file": (filename, content, content_type)},
        ).json()

    def ingest_document(
        self,
        *,
        collection_id: str,
        canonical_uri: str,
        title: str,
        text: str,
        filename: str,
        pre_chunked: bool = True,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/ingest/document",
            data={
                "collection_id": collection_id,
                "title": title,
                "canonical_uri": canonical_uri,
                "pre_chunked": "true" if pre_chunked else "false",
            },
            files={
                "file": (
                    filename,
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
        mode: str = "hybrid",
        lexical_weight: float = 1.0,
        vector_weight: float = 1.0,
    ) -> list[dict[str, Any]]:
        payload = self._request(
            "POST",
            "/v1/search",
            json={
                "query": query,
                "collections": collections,
                "limit": limit,
                "mode": mode,
                "lexical_weight": lexical_weight,
                "vector_weight": vector_weight,
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
