from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.tender_research.rag.analysis_service import (
    _build_report_markdown,
    _finalize_analysis_status,
    _save_report,
    _slugify,
    _vector_store_path,
    analyze_tender,
)
from src.tender_research.rag.retriever import RagSearchHit
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


class TestVectorStorePath:
    def test_default_format(self):
        class FakeConfig:
            rag_vector_store_path = "{provider}_{model}.json"
            data_dir = "/tmp"
            rag_embeddings_provider = "hashing"
        path = _vector_store_path(FakeConfig(), provider_name="hash", model_name="local-hash-v1")
        assert path.endswith("hash_local_hash_v1.json") or "hash_local_hash_v1" in path

    def test_default_path_when_no_format(self):
        class FakeConfig:
            rag_vector_store_path = None
            data_dir = "/tmp"
            rag_embeddings_provider = "hashing"
        path = _vector_store_path(FakeConfig(), provider_name="hash", model_name="local-hash-v1")
        assert "vector_store" in path


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


class TestAnalyzeTender:
    def test_finalize_analysis_status_adds_warning_when_sources_missing(self):
        status, warnings = _finalize_analysis_status(
            sections=[],
            sources_count=0,
            warnings=[],
            errors=[],
            use_llm=True,
        )

        assert status == "completed_with_warnings"
        assert warnings == ["Analysis completed, but no cited sources were found."]

    def test_no_tender_found(self):
        with patch(
            "src.tender_research.rag.analysis_service._get_session"
        ) as mock_session:
            mock_repo = MagicMock()
            mock_repo.get_tender_by_registry_number.return_value = None
            mock_repo.get_tender_by_external.return_value = None
            with patch(
                "src.tender_research.rag.analysis_service.TenderRepository",
                return_value=mock_repo,
            ):
                result = analyze_tender(
                    registry_number="nonexistent-123",
                    session=MagicMock(),
                )
                assert result.status == "no_context"
                assert "not found" in " ".join(result.errors).lower()

    def test_no_embeddings(self):
        with patch(
            "src.tender_research.rag.analysis_service._get_session"
        ) as mock_session:
            mock_repo = MagicMock()
            mock_repo.get_tender_by_registry_number.return_value = MagicMock()
            mock_repo.get_tender_by_external.return_value = MagicMock()
            mock_repo.count_document_embeddings.return_value = 0
            with patch(
                "src.tender_research.rag.analysis_service.TenderRepository",
                return_value=mock_repo,
            ):
                result = analyze_tender(
                    registry_number="123",
                    provider="hashing",
                    model="local-hash-v1",
                    session=MagicMock(),
                )
                assert result.status == "no_context"
                assert any("embeddings" in e.lower() for e in result.errors)

    def test_retrieval_only_mode(self):
        mock_tender = MagicMock()
        mock_tender.title = "Test Tender"

        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = mock_tender
        mock_repo.get_tender_by_external.return_value = mock_tender
        mock_repo.count_document_embeddings.return_value = 10

        mock_emb_provider = MagicMock()
        mock_emb_provider.provider_name = "hashing"
        mock_emb_provider.model_name = "local-hash-v1"
        mock_emb_provider.dimension = 8

        mock_vector_store = MagicMock()

        mock_retriever = MagicMock()
        mock_retriever.search_documents.return_value = []

        with patch(
            "src.tender_research.rag.analysis_service._get_session"
        ) as mock_session:
            with patch(
                "src.tender_research.rag.analysis_service.TenderRepository",
                return_value=mock_repo,
            ):
                with patch(
                    "src.tender_research.rag.analysis_service.build_embedding_provider",
                    return_value=mock_emb_provider,
                ):
                    with patch(
                        "src.tender_research.rag.analysis_service.JsonVectorStore",
                        return_value=mock_vector_store,
                    ):
                        with patch(
                            "src.tender_research.rag.analysis_service.RagRetriever",
                            return_value=mock_retriever,
                        ):
                            result = analyze_tender(
                                registry_number="123",
                                provider="hashing",
                                model="local-hash-v1",
                                session=MagicMock(),
                                use_llm=False,
                            )
                            assert result.status in (
                                "completed",
                                "completed_with_warnings",
                            )
                            assert result.sections_count == len(ANALYSIS_SECTIONS)
                            assert result.registry_number == "123"

    def test_with_search_hits_retrieval_only(self):
        mock_tender = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = mock_tender
        mock_repo.get_tender_by_external.return_value = mock_tender
        mock_repo.count_document_embeddings.return_value = 10

        mock_emb_provider = MagicMock()
        mock_emb_provider.provider_name = "hashing"
        mock_emb_provider.model_name = "local-hash-v1"
        mock_emb_provider.dimension = 8

        mock_vector_store = MagicMock()
        mock_retriever = MagicMock()

        hit = RagSearchHit(
            chunk_id="chunk-1",
            score=0.95,
            registry_number="123",
            tender_id="tender-1",
            tender_title="Test Tender",
            customer_name="Test Customer",
            document_id="doc-1",
            file_name="test.pdf",
            chunk_index=0,
            preview="Test preview content...",
            text="Test content for retrieval only mode.",
        )
        mock_retriever.search_documents.return_value = [hit]

        with patch(
            "src.tender_research.rag.analysis_service._get_session"
        ) as mock_session:
            with patch(
                "src.tender_research.rag.analysis_service.TenderRepository",
                return_value=mock_repo,
            ):
                with patch(
                    "src.tender_research.rag.analysis_service.build_embedding_provider",
                    return_value=mock_emb_provider,
                ):
                    with patch(
                        "src.tender_research.rag.analysis_service.JsonVectorStore",
                        return_value=mock_vector_store,
                    ):
                        with patch(
                            "src.tender_research.rag.analysis_service.RagRetriever",
                            return_value=mock_retriever,
                        ):
                            result = analyze_tender(
                                registry_number="123",
                                provider="hashing",
                                model="local-hash-v1",
                                session=MagicMock(),
                                use_llm=False,
                            )
                            assert result.status in (
                                "completed",
                                "completed_with_warnings",
                            )
                            assert result.sections_count == len(ANALYSIS_SECTIONS)
                            assert any(
                                s.status == "retrieval_only"
                                for s in result.sections
                            )

    def test_report_saving(self):
        mock_tender = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = mock_tender
        mock_repo.get_tender_by_external.return_value = mock_tender
        mock_repo.count_document_embeddings.return_value = 10

        mock_emb_provider = MagicMock()
        mock_emb_provider.provider_name = "hashing"
        mock_emb_provider.model_name = "local-hash-v1"
        mock_emb_provider.dimension = 8

        mock_vector_store = MagicMock()
        mock_retriever = MagicMock()
        mock_retriever.search_documents.return_value = []

        with patch(
            "src.tender_research.rag.analysis_service._get_session"
        ) as mock_session:
            with patch(
                "src.tender_research.rag.analysis_service.TenderRepository",
                return_value=mock_repo,
            ):
                with patch(
                    "src.tender_research.rag.analysis_service.build_embedding_provider",
                    return_value=mock_emb_provider,
                ):
                    with patch(
                        "src.tender_research.rag.analysis_service.JsonVectorStore",
                        return_value=mock_vector_store,
                    ):
                        with patch(
                            "src.tender_research.rag.analysis_service.RagRetriever",
                            return_value=mock_retriever,
                        ):
                            with patch(
                                "src.tender_research.rag.analysis_service._save_report"
                            ) as mock_save:
                                mock_save.return_value = "/tmp/report.md"
                                result = analyze_tender(
                                    registry_number="123",
                                    provider="hashing",
                                    model="local-hash-v1",
                                    session=MagicMock(),
                                    use_llm=False,
                                    save_report=True,
                                )
                                assert result.report_path is not None
                                mock_save.assert_called_once()
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
                return_value="tender-agent:tender-1:rev",
            ),
            patch(
                "src.tender_research.rag.analysis_service.build_data_platform_client",
                return_value=platform_client,
            ),
            patch(
                "src.tender_research.rag.analysis_service.DataPlatformRagRetriever",
                return_value=retriever,
            ),
            patch(
                "src.tender_research.rag.analysis_service.build_embedding_provider"
            ) as local_embeddings,
            patch(
                "src.tender_research.rag.analysis_service.JsonVectorStore"
            ) as json_store,
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
        local_embeddings.assert_not_called()
        json_store.assert_not_called()
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
                return_value="tender-agent:tender-1:rev",
            ),
            patch(
                "src.tender_research.rag.analysis_service.build_data_platform_client",
                return_value=platform_client,
            ),
            patch(
                "src.tender_research.rag.analysis_service.RagRetriever"
            ) as legacy_retriever,
        ):
            result = analyze_tender(
                registry_number="123",
                session=MagicMock(),
                record_history=False,
            )

        assert result.status == "no_context"
        assert any("Data Platform index" in error for error in result.errors)
        legacy_retriever.assert_not_called()
