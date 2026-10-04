from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.tender_research.rag.analysis_service import (
    _build_report_markdown,
    _finalize_analysis_status,
    _focused_queries_for_section,
    _notice_source_facts,
    _preserve_structured_deadline,
    _save_report,
    _slugify,
    _structured_fact_citation,
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


def test_deadline_answer_preserves_structured_source_timezone():
    answer = (
        "Дата окончания подачи заявок — 05.10.2026 10:00. "
        "Дата подведения итогов — 07.10.2026."
    )
    enriched = _preserve_structured_deadline(
        "deadlines",
        answer,
        "Окончание подачи заявок: 05.10.2026 10:00 (МСК+2)",
    )
    assert "05.10.2026 10:00 (МСК+2)" in enriched
    assert "05.10.2026 10:00." not in enriched


def test_application_and_restrictions_use_focused_retrieval_queries():
    subject_queries = " ".join(_focused_queries_for_section("subject")).lower()
    application_queries = " ".join(_focused_queries_for_section("application_composition")).lower()
    restrictions_queries = " ".join(_focused_queries_for_section("restrictions_benefits")).lower()
    assert "условная единица" in subject_queries
    assert "количество" in subject_queries
    assert "реестровой записи российского программного обеспечения" in application_queries
    assert "предложение о цене" in application_queries
    assert "1875" in restrictions_queries
    assert "ч. 3 ст. 30" in restrictions_queries
    assert "8.1 статьи 96" in restrictions_queries


def test_notice_source_facts_extract_position_and_procurement_advantage(tmp_path):
    title = "Оказание услуг по разработке модуля для ГИС Аксиома"
    notice = (
        "Объект закупки\n"
        "Наименование товара, работы, услугиКод позицииТип позицииЕдиница измерения"
        "Цена за единицуЗаказчикКоличество (объем работы, услуги)Стоимость позиции"
        f"{title}Идентификатор: 22318524862.02.30.000"
        "УслугаУсловная единица521000.00"
        "ДЕПАРТАМЕНТ ПРИРОДНЫХ РЕСУРСОВ - ЮГРЫ"
        "1521000.00"
        "Характеристики товара, работы, услуги"
        "Преимущества Преимущество в соответствии с ч. 3 ст. 30 Закона № 44-ФЗ "
        "Постановление Правительства Российской Федерации № 1875 "
        "Запрет закупок товаров, работ, услуг иностранных лиц "
        "Обеспечение заявок не требуется "
        "Обеспечение гарантийных обязательств не требуется"
    )
    path = tmp_path / "Извещение.txt"
    path.write_text(notice, encoding="utf-8")
    repo = MagicMock()
    repo.list_extracted_documents_by_tender.return_value = [
        SimpleNamespace(file_name="Извещение о закупке.docx", extracted_text_path=str(path))
    ]
    tender = SimpleNamespace(id="tender-1")

    facts = _notice_source_facts(repo, tender)

    assert "Единица измерения: Условная единица" in facts
    assert "Количество (объём): 1" in facts
    assert "Цена за единицу: 521000.00 RUB" in facts
    assert "Стоимость позиции: 521000.00 RUB" in facts
    assert "ОКПД2: 62.02.30.000" in facts
    assert "ч. 3 ст. 30 Закона № 44-ФЗ" in facts
    assert "Обеспечение заявки: не требуется" in facts
    assert "Обеспечение гарантийных обязательств: не требуется" in facts


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
        assert "Уникальных источников (включая структурированную карточку)" in result

    def test_report_surfaces_structured_source_facts_before_llm_sections(self):
        result = _build_report_markdown(
            registry_number="123",
            sections=[],
            used_llm=True,
            llm_model="model",
            retrieval_provider="hash",
            retrieval_model="v1",
            source_facts=(
                "Способ закупки: Запрос котировок\n"
                "Окончание подачи заявок: 05.10.2026 10:00 (МСК+2)\n"
                "НМЦК: 521000 RUB"
            ),
        )
        assert "## Подтверждённые факты карточки закупки" in result
        assert "- Способ закупки: Запрос котировок" in result
        assert "- Окончание подачи заявок: 05.10.2026 10:00 (МСК+2)" in result
        assert "- НМЦК: 521000 RUB" in result

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
    def test_structured_card_fact_citation_is_explicit_source(self):
        citation = _structured_fact_citation(
            registry_number="0187200001726001304",
            tender_title="Разработка ПО",
            customer_name="Заказчик",
            source_facts="Способ закупки: Запрос котировок",
        )
        assert citation.chunk_id == "structured-facts:0187200001726001304"
        assert citation.document_file_name == "Карточка ЕИС — структурированные факты"
        assert citation.quote_preview == "Способ закупки: Запрос котировок"

    def test_analysis_refreshes_latest_operator_run_before_using_rag_tender(self):
        mock_tender = MagicMock()
        mock_tender.raw_payload = {}
        mock_repo = MagicMock()
        mock_repo.count_document_embeddings.return_value = 0
        with patch(
            "src.tender_research.rag.analysis_service.TenderRepository",
            return_value=mock_repo,
        ):
            with patch(
                "src.tender_research.rag.analysis_service.sync_tender_from_operator_run",
                return_value=mock_tender,
            ) as sync:
                result = analyze_tender(
                    registry_number="0187200001726001304",
                    provider="hashing",
                    model="local-hash-v1",
                    session=MagicMock(),
                )
        sync.assert_called_once_with(mock_repo, "0187200001726001304")
        assert result.status == "no_context"
        mock_repo.get_tender_by_registry_number.assert_not_called()

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
