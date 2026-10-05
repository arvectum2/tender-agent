"""Tender RAG package.

The production Data Platform path must stay independent from the legacy local
RAG implementation. Historical package-level exports are resolved lazily so
older callers can still opt into the compatibility backend without importing
that stack during normal package initialization.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "BaseEmbeddingProvider": (
        "src.tender_research.rag.embeddings",
        "BaseEmbeddingProvider",
    ),
    "ChunkDraft": ("src.tender_research.rag.chunker", "ChunkDraft"),
    "ChunkingConfig": ("src.tender_research.rag.chunker", "ChunkingConfig"),
    "DocumentChunkIndexer": (
        "src.tender_research.rag.indexer",
        "DocumentChunkIndexer",
    ),
    "DocumentEmbeddingIndexer": (
        "src.tender_research.rag.indexer",
        "DocumentEmbeddingIndexer",
    ),
    "EmbeddingProviderError": (
        "src.tender_research.rag.embeddings",
        "EmbeddingProviderError",
    ),
    "EmbeddingServerUnavailableError": (
        "src.tender_research.rag.embeddings",
        "EmbeddingServerUnavailableError",
    ),
    "HashingEmbeddingProvider": (
        "src.tender_research.rag.embeddings",
        "HashingEmbeddingProvider",
    ),
    "JsonVectorStore": ("src.tender_research.rag.vector_store", "JsonVectorStore"),
    "LlamaCppEmbeddingProvider": (
        "src.tender_research.rag.embeddings",
        "LlamaCppEmbeddingProvider",
    ),
    "LocalChatLlmClient": ("src.tender_research.rag.llm", "LocalChatLlmClient"),
    "RagAnswer": ("src.tender_research.rag.llm", "RagAnswer"),
    "RagRetriever": ("src.tender_research.rag.retriever", "RagRetriever"),
    "RagSearchHit": ("src.tender_research.rag.search_types", "RagSearchHit"),
    "SearchResult": ("src.tender_research.rag.vector_store", "SearchResult"),
    "SourceCitation": ("src.tender_research.rag.llm", "SourceCitation"),
    "SentenceTransformersEmbeddingProvider": (
        "src.tender_research.rag.embeddings",
        "SentenceTransformersEmbeddingProvider",
    ),
    "build_embedding_provider": (
        "src.tender_research.rag.embeddings",
        "build_embedding_provider",
    ),
    "build_source_citations": (
        "src.tender_research.rag.llm",
        "build_source_citations",
    ),
    "chunk_text": ("src.tender_research.rag.chunker", "chunk_text"),
    "probe_embedding_provider": (
        "src.tender_research.rag.embeddings",
        "probe_embedding_provider",
    ),
    "resolve_embedding_dimension": (
        "src.tender_research.rag.embeddings",
        "resolve_embedding_dimension",
    ),
}

__all__ = [
    "BaseEmbeddingProvider",
    "ChunkDraft",
    "ChunkingConfig",
    "DocumentChunkIndexer",
    "DocumentEmbeddingIndexer",
    "EmbeddingProviderError",
    "EmbeddingServerUnavailableError",
    "HashingEmbeddingProvider",
    "JsonVectorStore",
    "LlamaCppEmbeddingProvider",
    "LocalChatLlmClient",
    "RagAnswer",
    "RagRetriever",
    "RagSearchHit",
    "SearchResult",
    "SentenceTransformersEmbeddingProvider",
    "SourceCitation",
    "build_embedding_provider",
    "build_source_citations",
    "chunk_text",
    "probe_embedding_provider",
    "resolve_embedding_dimension",
]


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
