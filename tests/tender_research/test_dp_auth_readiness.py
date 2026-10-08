"""Original RI223 HTTP 401 must not be reinterpreted as missing Data Platform index."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.tender_research.config import TenderResearchConfig
from src.tender_research.rag.analysis_service import analyze_tender
from src.tender_research.rag.data_platform import DataPlatformError


def _analyze_with_stats(outcome):
    tender = SimpleNamespace(id="source-bound", law_type="223fz", raw_payload={})
    repo = MagicMock()
    repo.get_tender_by_registry_number.return_value = tender
    repo.count_chunks_by_tender.return_value = 300
    client = MagicMock()
    if isinstance(outcome, Exception):
        client.collection_stats.side_effect = outcome
    else:
        client.collection_stats.return_value = outcome
    with (
        patch(
            "src.tender_research.rag.analysis_service.TenderRepository",
            return_value=repo,
        ),
        patch(
            "src.tender_research.rag.analysis_service.load_config",
            return_value=TenderResearchConfig(rag_retrieval_backend="data_platform"),
        ),
        patch(
            "src.tender_research.rag.analysis_service.build_tender_collection_id",
            return_value="tender:source:original",
        ),
        patch(
            "src.tender_research.rag.analysis_service.build_data_platform_client",
            return_value=client,
        ),
    ):
        result = analyze_tender(
            "32616445795",
            session=MagicMock(),
            use_llm=False,
            record_history=False,
        )
    client.close.assert_called_once()
    return result


@pytest.mark.parametrize("status", [401, 403])
def test_original_data_platform_auth_error_is_failed_not_missing_index(status):
    result = _analyze_with_stats(
        DataPlatformError(
            f"Data Platform GET /v1/collections/original/stats returned HTTP {status}: "
            '{"detail":"invalid internal API key"}'
        )
    )
    assert result.status == "failed"
    assert result.sections_count == 0
    assert result.sources_count == 0
    assert result.errors and "access denied" in result.errors[0]
    assert "readiness is UNKNOWN" in result.errors[0]
    assert (
        "invalid internal API key" not in result.errors[0]
    )  # don't leak upstream details
    assert "Run tender preparation first" not in result.errors[0]


@pytest.mark.parametrize(
    "failure",
    [
        DataPlatformError(
            "Data Platform GET original/stats returned HTTP 503: internal error"
        ),
        DataPlatformError("Data Platform request failed: connection refused"),
        ValueError("unexpected internal collection stats"),
        TypeError("bad resources shape"),
    ],
)
def test_unavailable_or_invalid_platform_stats_never_masquerade_as_empty_index(failure):
    result = _analyze_with_stats(failure)
    assert result.status == "failed"
    assert result.errors
    assert (
        "readiness is UNKNOWN" in result.errors[0]
        or "Index readiness is UNKNOWN" in result.errors[0]
    )
    assert "Run tender preparation first" not in result.errors[0]


def test_true_http_404_remains_empty_index_not_auth_failure():
    result = _analyze_with_stats(
        DataPlatformError(
            "Data Platform GET original/stats returned HTTP 404: collection not found"
        )
    )
    assert result.status == "no_context"
    assert "index is not prepared" in result.errors[0]
    assert "access denied" not in result.errors[0]


def test_existing_incomplete_embeddings_still_report_missing_index():
    result = _analyze_with_stats({"resources": 300, "embeddings": 299})
    assert result.status == "no_context"
    assert "index is not prepared" in result.errors[0]
