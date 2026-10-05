from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.tender_research.rag.prepare_service import (
    TenderPreparationResult,
    TenderPreparationStep,
    check_preparation_status,
    prepare_tender_for_analysis,
)


@pytest.fixture()
def mock_tender():
    tender = MagicMock()
    tender.id = "tender-1"
    tender.source = "eis"
    tender.external_id = "0323100010326000013"
    tender.registry_number = "0323100010326000013"
    tender.documents = []
    return tender


def test_result_and_step_contract() -> None:
    step = TenderPreparationStep("download_documents", "completed", "ok")
    result = TenderPreparationResult(
        registry_number="123",
        ready_for_analysis=True,
        steps=[step],
    )
    assert result.registry_number == "123"
    assert result.ready_for_analysis is True
    assert result.steps[0].name == "download_documents"


def test_prepare_uses_data_platform_for_processing_and_indexing(mock_tender) -> None:
    from src.tender_research.config import TenderResearchConfig
    from src.tender_research.rag.data_platform import (
        DataPlatformIndexSummary,
        DataPlatformProjectionSummary,
    )

    repo = MagicMock()
    repo.get_tender_by_registry_number.return_value = mock_tender
    repo.count_chunks_by_tender.return_value = 2
    repo.count_extracted_documents_by_tender.return_value = 1
    doc = MagicMock(
        download_status="downloaded",
        text_extraction_status="extracted",
        extracted_text_path="/tmp/test.txt",
    )
    mock_tender.documents = [doc]

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    projector = MagicMock()
    projector.build_for_tender.return_value = DataPlatformProjectionSummary(
        documents_seen=1,
        documents_processed=1,
        documents_skipped_existing=0,
        documents_failed=0,
        extracted_documents=1,
        chunks_projected=2,
        chunks_pruned=0,
    )
    indexer = MagicMock()
    indexer.build_for_tender.return_value = DataPlatformIndexSummary(
        collection_id="tender:tender-1:rev",
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
        patch("src.tender_research.rag.prepare_service.TenderRepository", return_value=repo),
        patch("src.tender_research.rag.prepare_service.load_config", return_value=config),
        patch(
            "src.tender_research.rag.prepare_service.download_tender_documents",
            return_value={"downloaded": 0, "failed": 0},
        ) as download,
        patch(
            "src.tender_research.rag.prepare_service.build_data_platform_client",
            return_value=client,
        ),
        patch(
            "src.tender_research.rag.prepare_service.DataPlatformDocumentProjector",
            return_value=projector,
        ),
        patch(
            "src.tender_research.rag.prepare_service.DataPlatformTenderIndexer",
            return_value=indexer,
        ),
    ):
        result = prepare_tender_for_analysis(
            "0323100010326000013",
            session=MagicMock(),
        )

    assert result.status == "completed"
    assert result.ready_for_analysis is True
    assert result.embeddings_total == 2
    download.assert_called_once()
    assert "extract_locally" not in download.call_args.kwargs
    projector.build_for_tender.assert_called_once()
    indexer.build_for_tender.assert_called_once_with("tender-1")


def test_status_requires_complete_data_platform_collection(mock_tender) -> None:
    from src.tender_research.config import TenderResearchConfig

    repo = MagicMock()
    repo.get_tender_by_registry_number.return_value = mock_tender
    repo.count_extracted_documents_by_tender.return_value = 1
    repo.count_chunks_by_tender.return_value = 2
    mock_tender.documents = [MagicMock(download_status="downloaded")]

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.collection_stats.return_value = {"resources": 1, "embeddings": 1}
    config = TenderResearchConfig(rag_retrieval_backend="data_platform")

    with (
        patch("src.tender_research.rag.prepare_service.TenderRepository", return_value=repo),
        patch("src.tender_research.rag.prepare_service.load_config", return_value=config),
        patch(
            "src.tender_research.rag.prepare_service.build_tender_collection_id",
            return_value="tender:tender-1:rev",
        ),
        patch(
            "src.tender_research.rag.prepare_service.build_data_platform_client",
            return_value=client,
        ),
    ):
        status = check_preparation_status(
            "0323100010326000013",
            session=MagicMock(),
        )

    assert status["ready_for_analysis"] is False
    assert "data_platform_index" in status["missing"]
    assert status["retrieval_backend"] == "data_platform"


def test_status_without_tender_is_not_ready() -> None:
    repo = MagicMock()
    repo.get_tender_by_registry_number.return_value = None
    with patch(
        "src.tender_research.rag.prepare_service.TenderRepository",
        return_value=repo,
    ):
        status = check_preparation_status("missing", session=MagicMock())
    assert status["tender_found"] is False
    assert status["ready_for_analysis"] is False
