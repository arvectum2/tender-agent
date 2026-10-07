from __future__ import annotations

from src.tender_research.rag.analysis_service import (
    _resolve_analysis_mode_config,
    build_section_context,
)
from src.tender_research.rag.search_types import RagSearchHit


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
