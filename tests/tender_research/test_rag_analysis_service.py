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
