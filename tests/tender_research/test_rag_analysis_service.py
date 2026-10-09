from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.tender_research.rag.analysis_service import (
    _build_report_markdown,
    _save_report,
    _slugify,
    analyze_tender,
)
from src.tender_research.rag.schemas import (
    ANALYSIS_SECTIONS,
    TenderAnalysisSection,
)


class TestSlugify:
    def test_simple(self):
        assert _slugify("Hello World") == "hello_world"

    def test_special_chars(self):
        assert _slugify("qwen2.5-14b") == "qwen2_5_14b"

    def test_empty(self):
        assert _slugify("") == "default"


class TestBuildReportMarkdown:
    def test_empty_sections(self):
        result = _build_report_markdown(
            registry_number="123",
            sections=[],
            used_llm=False,
            llm_model=None,
            retrieval_provider="hash",
            retrieval_model="v1",
        )
        assert "123" in result
        assert "0" in result

    def test_section_with_answer_and_sources(self):
        sections = [
            TenderAnalysisSection(
                id="01_notice_info",
                title="Информация об извещении",
                question="Тестовый вопрос",
                answer="Тестовый ответ",
                sources=[],
                status="completed",
            )
        ]
        result = _build_report_markdown(
            registry_number="123",
            sections=sections,
            used_llm=True,
            llm_model="qwen-test",
            retrieval_provider="hash",
            retrieval_model="v1",
        )
        assert "01_notice_info" in result
        assert "Тестовый ответ" in result
        assert "qwen-test" in result

    def test_insufficient_context(self):
        sections = [
            TenderAnalysisSection(
                id="01_notice_info",
                title="Информация об извещении",
                question="Тестовый вопрос",
                answer="",
                sources=[],
                status="insufficient_context",
            )
        ]
        result = _build_report_markdown("123", sections, True, "qwen", "hash", "v1")
        assert "Недостаточно контекста" in result

    def test_no_context(self):
        sections = [
            TenderAnalysisSection(
                id="01_notice_info",
                title="Информация об извещении",
                question="Тестовый вопрос",
                answer="",
                sources=[],
                status="no_context",
            )
        ]
        result = _build_report_markdown("123", sections, False, None, "hash", "v1")
        assert "Нет документов для анализа" in result


class TestSaveReport:
    def test_save_report_uses_unique_file_per_run(self, tmp_path):
        first_path = _save_report("# First", "123", str(tmp_path), run_token="run-a")
        second_path = _save_report("# Second", "123", str(tmp_path), run_token="run-b")

        assert first_path != second_path
        assert Path(first_path).read_text(encoding="utf-8") == "# First"
        assert Path(second_path).read_text(encoding="utf-8") == "# Second"
        assert Path(first_path).name.startswith("analyze_tender_123_")
        assert Path(second_path).name.startswith("analyze_tender_123_")


class TestDataPlatformAnalysis:
    def test_analysis_uses_data_platform_retriever_without_json_store(self):
        from src.tender_research.config import TenderResearchConfig

        mock_tender = MagicMock()
        mock_tender.id = "tender-1"
        mock_tender.title = "Test Tender"

        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = mock_tender
        mock_repo.get_tender_by_external.return_value = mock_tender
        mock_repo.count_chunks_by_tender.return_value = 2

        platform_client = MagicMock()
        platform_client.collection_stats.return_value = {
            "resources": 2,
            "embeddings": 2,
        }
        retriever = MagicMock()
        retriever.search_documents.return_value = []

        config = TenderResearchConfig(
            rag_retrieval_backend="data_platform",
            rag_data_platform_base_url="http://data-platform.test",
        )

        with (
            patch(
                "src.tender_research.rag.analysis_service.TenderRepository",
                return_value=mock_repo,
            ),
            patch(
                "src.tender_research.rag.analysis_service.load_config",
                return_value=config,
            ),
            patch(
                "src.tender_research.rag.analysis_service.build_tender_collection_id",
                return_value="tender:tender-1:rev",
            ),
            patch(
                "src.tender_research.rag.analysis_service.build_data_platform_client",
                return_value=platform_client,
            ),
            patch(
                "src.tender_research.rag.analysis_service.DataPlatformRagRetriever",
                return_value=retriever,
            ),
        ):
            result = analyze_tender(
                registry_number="123",
                session=MagicMock(),
                use_llm=False,
                record_history=False,
            )

        assert result.retrieval_provider == "data_platform"
        assert result.retrieval_model == "hybrid"
        assert result.sections_count == len(ANALYSIS_SECTIONS)
        platform_client.close.assert_called_once()

    def test_analysis_fails_closed_for_incomplete_platform_index(self):
        from src.tender_research.config import TenderResearchConfig

        mock_tender = MagicMock()
        mock_tender.id = "tender-1"
        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = mock_tender
        mock_repo.get_tender_by_external.return_value = mock_tender
        mock_repo.count_chunks_by_tender.return_value = 2

        platform_client = MagicMock()
        platform_client.collection_stats.return_value = {
            "resources": 1,
            "embeddings": 1,
        }
        config = TenderResearchConfig(rag_retrieval_backend="data_platform")

        with (
            patch(
                "src.tender_research.rag.analysis_service.TenderRepository",
                return_value=mock_repo,
            ),
            patch(
                "src.tender_research.rag.analysis_service.load_config",
                return_value=config,
            ),
            patch(
                "src.tender_research.rag.analysis_service.build_tender_collection_id",
                return_value="tender:tender-1:rev",
            ),
            patch(
                "src.tender_research.rag.analysis_service.build_data_platform_client",
                return_value=platform_client,
            ),
        ):
            result = analyze_tender(
                registry_number="123",
                session=MagicMock(),
                record_history=False,
            )

        assert result.status == "no_context"
        assert any("Data Platform index" in error for error in result.errors)



def test_record_history_failure_rolls_back_shared_session(session):
    from unittest.mock import Mock, patch

    from sqlalchemy import text

    from src.tender_research.rag import analysis_service
    from src.tender_research.rag.schemas import TenderAnalysisResult

    original_rollback = session.rollback
    rollback_spy = Mock(side_effect=original_rollback)
    session.rollback = rollback_spy

    result = TenderAnalysisResult(
        status="completed",
        registry_number="0358200040626000014",
        sections=[],
        sections_count=0,
        sources_count=0,
        analysis_mode="fast",
    )
    with patch.object(
        analysis_service,
        "record_analysis_run",
        side_effect=RuntimeError("history write failed"),
    ):
        run_id = analysis_service._record_history(
            result,
            session,
            source="daily_tender_run:test",
        )

    assert run_id is None
    rollback_spy.assert_called_once()
    assert session.scalar(text("select 1")) == 1



def test_record_history_normalizes_oversize_source(session):
    import json

    from src.tender_research.rag.history_service import record_analysis_run

    source = "daily_tender_run:DTR-20261006T171139Z-79cfe20b"
    row = record_analysis_run(
        session,
        registry_number="0358200040626000014",
        status="completed",
        source=source,
        metadata={"analysis_mode": "balanced"},
    )

    assert row.source is not None
    assert len(row.source) <= 32
    assert json.loads(row.metadata_json or "{}") == {
        "analysis_mode": "balanced",
        "history_source_full": source,
    }


class TestRi223RegimeBoundAnalysis:
    def test_223fz_questions_do_not_require_44fz_eligibility(self):
        from src.tender_research.rag.schemas import analysis_sections_for_regime

        sections = analysis_sections_for_regime("223fz")
        assert len(sections) == len(ANALYSIS_SECTIONS)
        assert [s["id"] for s in sections] == [s["id"] for s in ANALYSIS_SECTIONS]
        assert sections is not ANALYSIS_SECTIONS
        assert sections[1]["question"] != ANALYSIS_SECTIONS[1]["question"]
        assert "фактический предмет" in sections[1]["question"].lower()
        assert "условия договора" in sections[5]["title"].lower()
        assert "СМСП" in sections[7]["question"]
        assert "223-ФЗ" in sections[2]["question"]
        assert "Не переносить правила 44-ФЗ" in sections[2]["question"]
        assert ANALYSIS_SECTIONS[2]["question"].endswith("44-ФЗ?")

    def test_other_regimes_keep_canonical_44fz_questions(self):
        from src.tender_research.rag.schemas import analysis_sections_for_regime

        for law_type in ("44fz", "private", "unknown", None):
            assert analysis_sections_for_regime(law_type) is ANALYSIS_SECTIONS

    def test_live_analyzer_dispatch_uses_ri223_document_questions(self):
        from src.tender_research.config import TenderResearchConfig
        from src.tender_research.rag.schemas import analysis_sections_for_regime

        tender = MagicMock()
        tender.id = "223-id"
        tender.title = "Tender"
        tender.law_type = "223fz"
        repo = MagicMock()
        repo.get_tender_by_registry_number.return_value = tender
        repo.count_chunks_by_tender.return_value = 2
        client = MagicMock()
        client.collection_stats.return_value = {"resources": 2, "embeddings": 2}
        retriever = MagicMock()
        retriever.search_documents.return_value = []
        with (
            patch("src.tender_research.rag.analysis_service.TenderRepository", return_value=repo),
            patch("src.tender_research.rag.analysis_service.load_config",
                  return_value=TenderResearchConfig(rag_retrieval_backend="data_platform")),
            patch("src.tender_research.rag.analysis_service.build_tender_collection_id",
                  return_value="tender:test"),
            patch("src.tender_research.rag.analysis_service.build_data_platform_client",
                  return_value=client),
            patch("src.tender_research.rag.analysis_service.DataPlatformRagRetriever",
                  return_value=retriever),
        ):
            result = analyze_tender("32616445795", session=MagicMock(),
                                    record_history=False, use_llm=False)

        expected = analysis_sections_for_regime("223fz")
        assert [s.question for s in result.sections] == [s["question"] for s in expected]
        assert retriever.search_documents.call_count == len(ANALYSIS_SECTIONS)
        assert result.sections_count == len(ANALYSIS_SECTIONS)
        assert result.used_llm is False
        client.close.assert_called_once()
