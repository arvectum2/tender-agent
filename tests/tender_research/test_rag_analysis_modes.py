from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.tender_research.rag.analysis_service import (
    _resolve_analysis_mode_config,
    analyze_tender,
    build_section_context,
)
from src.tender_research.rag.llm import RagAnswer
from src.tender_research.rag.retriever import RagSearchHit


@pytest.fixture(autouse=True)
def explicit_legacy_backend_for_legacy_analysis_tests(monkeypatch):
    from src.tender_research.config import TenderResearchConfig

    monkeypatch.setattr(
        "src.tender_research.rag.analysis_service.load_config",
        lambda: TenderResearchConfig(rag_retrieval_backend="legacy"),
    )


def _hit(*, chunk_id: str, text: str) -> RagSearchHit:
    return RagSearchHit(
        chunk_id=chunk_id,
        score=0.95,
        registry_number="123",
        tender_id="tender-1",
        tender_title="Тестовая закупка",
        customer_name="Тестовый заказчик",
        document_id=f"doc-{chunk_id}",
        file_name=f"{chunk_id}.pdf",
        chunk_index=0,
        preview=text[:120],
        text=text,
    )


def test_analysis_mode_presets_have_expected_defaults() -> None:
    fast = _resolve_analysis_mode_config(
        analysis_mode="fast",
        limit=None,
        max_context_chars_per_section=None,
        max_chunks_per_section=None,
        llm_timeout_seconds=None,
    )
    balanced = _resolve_analysis_mode_config(
        analysis_mode="balanced",
        limit=None,
        max_context_chars_per_section=None,
        max_chunks_per_section=None,
        llm_timeout_seconds=None,
    )
    detailed = _resolve_analysis_mode_config(
        analysis_mode="detailed",
        limit=None,
        max_context_chars_per_section=None,
        max_chunks_per_section=None,
        llm_timeout_seconds=None,
    )

    assert (fast.retrieval_limit, fast.max_context_chars_per_section) == (3, 4000)
    assert (balanced.retrieval_limit, balanced.max_context_chars_per_section) == (5, 7000)
    assert (detailed.retrieval_limit, detailed.max_context_chars_per_section) == (8, 12000)


def test_build_section_context_respects_limits_and_preserves_metadata() -> None:
    hits = [
        _hit(chunk_id="chunk-1", text="A" * 5000),
        _hit(chunk_id="chunk-2", text="B" * 5000),
        _hit(chunk_id="chunk-3", text="C" * 5000),
    ]

    context = build_section_context(
        hits,
        max_chunks=2,
        max_context_chars=3500,
        max_chunk_chars=2000,
        max_preview_chars=80,
    )

    assert context.chunks_considered == 2
    assert context.chunks_used >= 1
    assert context.context_chars <= 3500
    assert context.truncated_chunks >= 1
    assert context.hits[0].chunk_id == "chunk-1"
    assert context.hits[0].document_id == "doc-chunk-1"


def test_analyze_tender_llm_fallback_returns_timings_and_warning() -> None:
    mock_tender = MagicMock()
    mock_repo = MagicMock()
    mock_repo.get_tender_by_registry_number.return_value = mock_tender
    mock_repo.get_tender_by_external.return_value = mock_tender
    mock_repo.count_document_embeddings.return_value = 10

    mock_emb_provider = MagicMock()
    mock_emb_provider.provider_name = "hashing"
    mock_emb_provider.model_name = "local-hash-v1"
    mock_emb_provider.dimension = 8

    hit = _hit(chunk_id="chunk-1", text=("Требования к заявке и условия оплаты. " * 80).strip())

    class FakeRetriever:
        def search_documents(self, query, registry_number=None, limit=10):
            return [hit]

    class FakeLlmClient:
        def build_prompt_metrics(self, question, contexts, registry_number=None, analysis_mode="balanced"):
            return {
                "context_chars": 1400,
                "system_prompt_chars": 200,
                "user_prompt_chars": 300,
                "prompt_chars": 500,
            }

        def generate_answer(self, question, contexts, registry_number=None, analysis_mode="balanced"):
            return RagAnswer(
                answer="",
                sources=[],
                used_chunks_count=len(contexts),
                model="qwen-local",
                error="Local LLM request timed out.",
            )

    with patch("src.tender_research.rag.analysis_service.TenderRepository", return_value=mock_repo), patch(
        "src.tender_research.rag.analysis_service.build_embedding_provider",
        return_value=mock_emb_provider,
    ), patch(
        "src.tender_research.rag.analysis_service.JsonVectorStore",
        return_value=MagicMock(),
    ), patch(
        "src.tender_research.rag.analysis_service.RagRetriever",
        return_value=FakeRetriever(),
    ), patch(
        "src.tender_research.rag.analysis_service.LocalChatLlmClient",
        return_value=FakeLlmClient(),
    ):
        result = analyze_tender(
            registry_number="123",
            provider="hashing",
            model="local-hash-v1",
            session=MagicMock(),
            use_llm=True,
            analysis_mode="fast",
            record_history=False,
        )

    assert result.analysis_mode == "fast"
    assert result.status == "completed_with_warnings"
    assert result.sections_count > 0
    assert result.sources_count > 0
    assert result.llm_calls_count == result.sections_count
    assert result.duration_seconds is not None
    assert result.per_section_timings
    assert result.per_section_timings[0]["status"] == "retrieval_only_fallback"
    assert result.per_section_timings[0]["context_chars"] <= 4000
    assert any("LLM fallback for section" in warning for warning in result.warnings)
