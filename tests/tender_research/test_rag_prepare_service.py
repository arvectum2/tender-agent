from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from src.tender_research.rag.prepare_service import (
    TenderPreparationResult,
    TenderPreparationStep,
    check_preparation_status,
    prepare_tender_for_analysis,
)


@pytest.fixture(autouse=True)
def explicit_legacy_backend_for_legacy_tests(monkeypatch):
    from src.tender_research.config import TenderResearchConfig

    monkeypatch.setattr(
        "src.tender_research.rag.prepare_service.load_config",
        lambda: TenderResearchConfig(rag_retrieval_backend="legacy"),
    )


@pytest.fixture()
def mock_repo():
    return MagicMock()


@pytest.fixture()
def mock_tender():
    tender = MagicMock()
    tender.id = "tender-1"
    tender.source = "eis"
    tender.external_id = "0323100010326000013"
    tender.registry_number = "0323100010326000013"
    tender.documents = []
    return tender


@pytest.fixture()
def mock_session():
    return MagicMock()


class TestPrepareTenderForAnalysis:
    def test_tender_already_prepared_returns_completed(self, mock_session, mock_tender):
        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = mock_tender
        mock_repo.count_chunks_by_tender.return_value = 50
        mock_repo.count_embeddings_by_tender.return_value = 50
        mock_repo.count_extracted_documents_by_tender.return_value = 5
        mock_doc = MagicMock()
        mock_doc.download_status = "downloaded"
        mock_doc.text_extraction_status = "extracted"
        mock_doc.extracted_text_path = "/tmp/test.txt"
        mock_tender.documents = [mock_doc]

        with patch("src.tender_research.rag.prepare_service.TenderRepository", return_value=mock_repo):
            with patch("src.tender_research.rag.prepare_service.build_embedding_provider") as mock_build_emb:
                mock_provider = MagicMock()
                mock_provider.provider_name = "llama_cpp"
                mock_provider.model_name = "Qwen3-Embedding-4B"
                mock_build_emb.return_value = mock_provider
                result = prepare_tender_for_analysis(
                    "0323100010326000013",
                    session=mock_session,
                )

        assert result.status == "completed"
        assert result.ready_for_analysis is True
        assert result.registry_number == "0323100010326000013"

    def test_no_tender_ingest_fails(self, mock_session):
        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = None

        with patch("src.tender_research.rag.prepare_service.TenderRepository", return_value=mock_repo):
            with patch("src.tender_research.rag.prepare_service.EisTenderLoader") as mock_loader:
                mock_loader_instance = MagicMock()
                mock_loader_instance.fetch_by_registry_number.return_value = None
                mock_loader.return_value = mock_loader_instance
                result = prepare_tender_for_analysis(
                    "0000000000000000",
                    session=mock_session,
                )

        assert result.status == "no_tender"
        assert result.ready_for_analysis is False

    def test_ingest_success(self, mock_session):
        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.side_effect = [None, None]
        mock_tender = MagicMock()
        mock_tender.id = "tender-2"
        mock_tender.source = "eis"
        mock_tender.external_id = "0323100010326000013"
        mock_tender.registry_number = "0323100010326000013"
        mock_tender.documents = []
        mock_repo.upsert_tender.return_value = mock_tender
        mock_repo.count_chunks_by_tender.return_value = 30
        mock_repo.count_embeddings_by_tender.return_value = 30
        mock_repo.count_extracted_documents_by_tender.return_value = 3
        mock_doc = MagicMock()
        mock_doc.download_status = "downloaded"
        mock_doc.text_extraction_status = "extracted"
        mock_doc.extracted_text_path = "/tmp/test.txt"
        mock_tender.documents = [mock_doc]

        raw_tender = MagicMock()
        raw_tender.registry_number = "0323100010326000013"
        raw_tender.external_id = "0323100010326000013"
        raw_tender.title = "Test Tender"
        raw_tender.description = "Test"
        raw_tender.customer_name = "Test Customer"
        raw_tender.customer_inn = None
        raw_tender.law_type = "44-fz"
        raw_tender.nmck_amount = 100000.0
        raw_tender.currency = "RUB"
        raw_tender.publication_date = None
        raw_tender.application_deadline = None
        raw_tender.status = "completed"
        raw_tender.raw_payload = {}
        raw_tender.documents = None

        def get_tender_side_effect(rn):
            if rn == "0323100010326000013":
                return mock_tender
            return None

        mock_repo.get_tender_by_registry_number.side_effect = get_tender_side_effect

        with patch("src.tender_research.rag.prepare_service.TenderRepository", return_value=mock_repo):
            with patch("src.tender_research.rag.prepare_service.EisTenderLoader") as mock_loader:
                mock_loader_instance = MagicMock()
                mock_loader_instance.fetch_by_registry_number.return_value = raw_tender
                mock_loader.return_value = mock_loader_instance
                with patch("src.tender_research.rag.prepare_service.build_embedding_provider") as mock_build_emb:
                    mock_provider = MagicMock()
                    mock_provider.provider_name = "llama_cpp"
                    mock_provider.model_name = "Qwen3-Embedding-4B"
                    mock_build_emb.return_value = mock_provider
                    with patch("src.tender_research.rag.prepare_service.download_tender_documents",
                               return_value={"downloaded": 0, "failed": 0}):
                        result = prepare_tender_for_analysis(
                            "0323100010326000013",
                            session=mock_session,
                        )

        assert result.status == "completed"
        assert result.tender_found is True

    def test_idempotent_repeated_call(self, mock_session, mock_tender):
        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = mock_tender
        mock_repo.count_chunks_by_tender.return_value = 50
        mock_repo.count_embeddings_by_tender.return_value = 50
        mock_repo.count_extracted_documents_by_tender.return_value = 5
        mock_doc = MagicMock()
        mock_doc.download_status = "downloaded"
        mock_doc.text_extraction_status = "extracted"
        mock_doc.extracted_text_path = "/tmp/test.txt"
        mock_tender.documents = [mock_doc]

        with patch("src.tender_research.rag.prepare_service.TenderRepository", return_value=mock_repo):
            with patch("src.tender_research.rag.prepare_service.build_embedding_provider") as mock_build_emb:
                mock_provider = MagicMock()
                mock_provider.provider_name = "llama_cpp"
                mock_provider.model_name = "Qwen3-Embedding-4B"
                mock_build_emb.return_value = mock_provider
                result1 = prepare_tender_for_analysis(
                    "0323100010326000013",
                    session=mock_session,
                )
                result2 = prepare_tender_for_analysis(
                    "0323100010326000013",
                    session=mock_session,
                )

        assert result1.status == "completed"
        assert result2.status == "completed"
        assert result1.ready_for_analysis is True
        assert result2.ready_for_analysis is True
        assert result1.chunks_total == result2.chunks_total
        assert result1.embeddings_total == result2.embeddings_total
        assert mock_repo.upsert_tender.call_count == 0

    def test_no_chunks_result_no_embeddings(self, mock_session, mock_tender):
        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = mock_tender
        mock_repo.count_chunks_by_tender.return_value = 0
        mock_repo.count_embeddings_by_tender.return_value = 0
        mock_repo.count_extracted_documents_by_tender.return_value = 0
        mock_repo.list_extracted_documents_by_tender.return_value = []
        mock_doc = MagicMock()
        mock_doc.download_status = "downloaded"
        mock_doc.text_extraction_status = "extracted"
        mock_doc.extracted_text_path = "/tmp/test.txt"
        mock_tender.documents = [mock_doc]

        with patch("src.tender_research.rag.prepare_service.TenderRepository", return_value=mock_repo):
            with patch("src.tender_research.rag.prepare_service.build_embedding_provider") as mock_build_emb:
                mock_provider = MagicMock()
                mock_provider.provider_name = "llama_cpp"
                mock_provider.model_name = "Qwen3-Embedding-4B"
                mock_provider.dimension = 256
                mock_build_emb.return_value = mock_provider
                with patch("src.tender_research.rag.prepare_service.download_tender_documents",
                           return_value={"downloaded": 0, "failed": 0}):
                    result = prepare_tender_for_analysis(
                        "0323100010326000013",
                        session=mock_session,
                    )

        assert result.ready_for_analysis is False

    def test_check_readiness_ready(self, mock_session, mock_tender):
        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = mock_tender
        mock_repo.count_extracted_documents_by_tender.return_value = 3
        mock_repo.count_chunks_by_tender.return_value = 30
        mock_repo.count_embeddings_by_tender.return_value = 30
        mock_doc = MagicMock()
        mock_doc.download_status = "downloaded"
        mock_tender.documents = [mock_doc]

        with patch("src.tender_research.rag.prepare_service.TenderRepository", return_value=mock_repo):
            with patch("src.tender_research.rag.prepare_service.build_embedding_provider") as mock_build_emb:
                mock_provider = MagicMock()
                mock_provider.provider_name = "llama_cpp"
                mock_provider.model_name = "Qwen3-Embedding-4B"
                mock_build_emb.return_value = mock_provider
                status = check_preparation_status("0323100010326000013", session=mock_session)

        assert status["ready_for_analysis"] is True
        assert status["tender_found"] is True
        assert status["chunks_total"] == 30
        assert status["embeddings_total"] == 30
        assert status["missing"] == []

    def test_check_readiness_not_ready(self, mock_session, mock_tender):
        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = mock_tender
        mock_repo.count_extracted_documents_by_tender.return_value = 0
        mock_repo.count_chunks_by_tender.return_value = 0
        mock_repo.count_embeddings_by_tender.return_value = 0
        mock_tender.documents = []

        with patch("src.tender_research.rag.prepare_service.TenderRepository", return_value=mock_repo):
            with patch("src.tender_research.rag.prepare_service.build_embedding_provider") as mock_build_emb:
                mock_provider = MagicMock()
                mock_provider.provider_name = "llama_cpp"
                mock_provider.model_name = "Qwen3-Embedding-4B"
                mock_build_emb.return_value = mock_provider
                status = check_preparation_status("0323100010326000013", session=mock_session)

        assert status["ready_for_analysis"] is False
        assert "chunks" in status["missing"]
        assert "embeddings" in status["missing"]

    def test_check_readiness_no_tender(self, mock_session):
        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = None

        with patch("src.tender_research.rag.prepare_service.TenderRepository", return_value=mock_repo):
            with patch("src.tender_research.rag.prepare_service.build_embedding_provider") as mock_build_emb:
                mock_provider = MagicMock()
                mock_provider.provider_name = "llama_cpp"
                mock_provider.model_name = "Qwen3-Embedding-4B"
                mock_build_emb.return_value = mock_provider
                status = check_preparation_status("0000000000000000", session=mock_session)

        assert status["tender_found"] is False
        assert status["ready_for_analysis"] is False
        assert "tender" in status["missing"]
class TestDataPlatformPreparation:
    def test_prepare_uses_data_platform_without_local_embeddings(
        self,
        mock_session,
        mock_tender,
    ):
        from src.tender_research.config import TenderResearchConfig
        from src.tender_research.rag.data_platform import DataPlatformIndexSummary

        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = mock_tender
        mock_repo.count_chunks_by_tender.return_value = 2
        mock_repo.count_extracted_documents_by_tender.return_value = 1
        mock_doc = MagicMock()
        mock_doc.download_status = "downloaded"
        mock_doc.text_extraction_status = "extracted"
        mock_doc.extracted_text_path = "/tmp/test.txt"
        mock_tender.documents = [mock_doc]

        platform_client = MagicMock()
        platform_client.__enter__.return_value = platform_client
        platform_client.__exit__.return_value = None
        indexer = MagicMock()
        indexer.build_for_tender.return_value = DataPlatformIndexSummary(
            collection_id="tender-agent:tender-1:rev",
            chunks_seen=2,
            chunks_indexed=2,
            platform_chunks_created=2,
            embeddings_created=2,
        )

        config = TenderResearchConfig(
            rag_retrieval_backend="data_platform",
            rag_data_platform_base_url="http://data-platform.test",
        )

        with (
            patch(
                "src.tender_research.rag.prepare_service.TenderRepository",
                return_value=mock_repo,
            ),
            patch(
                "src.tender_research.rag.prepare_service.load_config",
                return_value=config,
            ),
            patch(
                "src.tender_research.rag.prepare_service.download_tender_documents",
                return_value={"downloaded": 0, "failed": 0},
            ),
            patch(
                "src.tender_research.rag.prepare_service.build_data_platform_client",
                return_value=platform_client,
            ),
            patch(
                "src.tender_research.rag.prepare_service.DataPlatformTenderIndexer",
                return_value=indexer,
            ),
            patch(
                "src.tender_research.rag.prepare_service.DataPlatformDocumentProjector"
            ),
            patch(
                "src.tender_research.rag.prepare_service.build_embedding_provider"
            ) as local_embeddings,
        ):
            result = prepare_tender_for_analysis(
                "0323100010326000013",
                session=mock_session,
            )

        assert result.status == "completed"
        assert result.ready_for_analysis is True
        assert result.embeddings_total == 2
        assert result.embeddings_created == 2
        local_embeddings.assert_not_called()

    def test_status_requires_complete_data_platform_collection(
        self,
        mock_session,
        mock_tender,
    ):
        from src.tender_research.config import TenderResearchConfig

        mock_repo = MagicMock()
        mock_repo.get_tender_by_registry_number.return_value = mock_tender
        mock_repo.count_extracted_documents_by_tender.return_value = 1
        mock_repo.count_chunks_by_tender.return_value = 2
        mock_tender.documents = [MagicMock(download_status="downloaded")]

        platform_client = MagicMock()
        platform_client.__enter__.return_value = platform_client
        platform_client.__exit__.return_value = None
        platform_client.collection_stats.return_value = {
            "resources": 1,
            "embeddings": 1,
        }

        config = TenderResearchConfig(
            rag_retrieval_backend="data_platform",
            rag_data_platform_base_url="http://data-platform.test",
        )

        with (
            patch(
                "src.tender_research.rag.prepare_service.TenderRepository",
                return_value=mock_repo,
            ),
            patch(
                "src.tender_research.rag.prepare_service.load_config",
                return_value=config,
            ),
            patch(
                "src.tender_research.rag.prepare_service.build_tender_collection_id",
                return_value="tender-agent:tender-1:rev",
            ),
            patch(
                "src.tender_research.rag.prepare_service.build_data_platform_client",
                return_value=platform_client,
            ),
        ):
            status = check_preparation_status(
                "0323100010326000013",
                session=mock_session,
            )

        assert status["ready_for_analysis"] is False
        assert "data_platform_index" in status["missing"]
        assert status["retrieval_backend"] == "data_platform"
