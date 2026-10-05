from __future__ import annotations

import re

from src.tender_research.rag.embeddings import BaseEmbeddingProvider
from src.tender_research.rag.search_types import RagSearchHit
from src.tender_research.rag.vector_store import JsonVectorStore
from src.tender_research.repository import TenderRepository

_TOKEN_RE = re.compile(r"[а-яёa-z0-9]{4,}", re.IGNORECASE)


class RagRetriever:
    def __init__(
        self,
        repo: TenderRepository,
        provider: BaseEmbeddingProvider,
        vector_store: JsonVectorStore,
    ):
        self._repo = repo
        self._provider = provider
        self._vector_store = vector_store

    def search_documents(
        self,
        query: str,
        *,
        tender_id: str | None = None,
        registry_number: str | None = None,
        customer_name: str | None = None,
        limit: int = 10,
    ) -> list[RagSearchHit]:
        return self._search_documents(
            query,
            tender_id=tender_id,
            registry_number=registry_number,
            customer_name=customer_name,
            limit=limit,
            allow_unscoped=False,
        )

    def search_all_documents(self, query: str, *, limit: int = 10) -> list[RagSearchHit]:
        """Explicit index-inspection search; procurement analysis must not call this."""
        return self._search_documents(query, limit=limit, allow_unscoped=True)

    def _search_documents(
        self,
        query: str,
        *,
        tender_id: str | None = None,
        registry_number: str | None = None,
        customer_name: str | None = None,
        limit: int = 10,
        allow_unscoped: bool,
    ) -> list[RagSearchHit]:
        if not query.strip():
            return []

        # Procurement analysis is a tenant-scoped operation.  A caller that
        # needs cross-tender research must opt into a separate API; silently
        # falling back to the global vector collection is never safe here.
        if not tender_id and registry_number:
            tender = self._repo.get_tender_by_registry_number(registry_number)
            tender_id = str(tender.id) if tender else None
            if not tender_id:
                # An unknown registry number has no owned chunks; returning an
                # empty result is safe and avoids any global fallback.
                return []
        if not tender_id and not allow_unscoped:
            raise ValueError("tender_id (or a resolvable registry_number) is required for procurement document retrieval")

        allowed_chunk_ids = None
        if tender_id:
            allowed = self._repo.list_chunk_ids_for_filters(
                tender_id=tender_id,
                registry_number=registry_number,
                customer_name=customer_name,
            )
            if not allowed:
                return []
            allowed_chunk_ids = set(allowed)

        query_vector = self._provider.embed_query(query)
        results = self._vector_store.search(
            query_vector,
            limit=limit,
            allowed_vector_ids=allowed_chunk_ids,
        )

        hits = self._build_hits(results)
        if hits:
            return hits
        return self._lexical_fallback(
            query,
            allowed_chunk_ids=allowed_chunk_ids,
            limit=limit,
        )

    def _build_hits(self, results) -> list[RagSearchHit]:
        hits: list[RagSearchHit] = []
        for result in results:
            context = self._repo.get_chunk_context(result.vector_id)
            if context is None:
                continue
            hits.append(self._context_to_hit(context, score=float(result.score)))
        return hits

    def _lexical_fallback(
        self,
        query: str,
        *,
        allowed_chunk_ids: set[str] | None,
        limit: int,
    ) -> list[RagSearchHit]:
        keywords = _extract_keywords(query)
        if not keywords:
            return []

        candidate_ids = (
            sorted(allowed_chunk_ids)
            if allowed_chunk_ids is not None
            else sorted(self._repo.list_chunk_ids_for_filters())
        )
        scored: list[tuple[float, dict]] = []
        normalized_query = _normalize_text(query)
        for chunk_id in candidate_ids:
            context = self._repo.get_chunk_context(chunk_id)
            if context is None:
                continue
            score = _lexical_score(
                keywords,
                normalized_query=normalized_query,
                context=context,
            )
            if score <= 0:
                continue
            scored.append((score, context))

        scored.sort(
            key=lambda item: (
                -item[0],
                item[1]["file_name"],
                item[1]["chunk_index"],
            )
        )
        return [
            self._context_to_hit(context, score=score)
            for score, context in scored[:limit]
        ]

    def _context_to_hit(self, context: dict, *, score: float) -> RagSearchHit:
        preview = context["text"][:280].replace("\n", " ").strip()
        return RagSearchHit(
            chunk_id=context["chunk_id"],
            score=score,
            registry_number=context["registry_number"],
            tender_id=context["tender_id"],
            tender_title=context["tender_title"],
            customer_name=context["customer_name"],
            document_id=context["document_id"],
            file_name=context["file_name"],
            chunk_index=context["chunk_index"],
            preview=preview,
            text=context["text"],
        )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace("ё", "е")).strip()


def _extract_keywords(query: str) -> list[str]:
    stopwords = {
        "какая",
        "какие",
        "каковы",
        "какой",
        "содержится",
        "содержанию",
        "установлены",
        "установлено",
        "входит",
        "входят",
        "должны",
        "нужно",
        "подается",
        "подаётся",
        "процедуры",
        "документации",
        "закупке",
        "закупки",
        "контракта",
        "контракту",
        "участие",
        "участникам",
        "заявок",
        "заявка",
        "документы",
        "документов",
    }
    result: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN_RE.findall(query.lower().replace("ё", "е")):
        if token in stopwords or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result


def _lexical_score(keywords: list[str], *, normalized_query: str, context: dict) -> float:
    haystack = _normalize_text(f"{context['file_name']} {context['text']}")
    if not haystack:
        return 0.0

    score = 0.0
    if normalized_query and normalized_query in haystack:
        score += 5.0

    for keyword in keywords:
        if keyword in haystack:
            score += 2.0 + min(len(keyword), 16) / 16.0

    return score
