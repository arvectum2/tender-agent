from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.tender_research.rag.data_platform import build_data_platform_client


def cfg(**kwargs):
    return SimpleNamespace(rag_data_platform_base_url="http://localhost:8094",
                           rag_data_platform_api_key="test-platform",
                           rag_data_platform_timeout_seconds=30, **kwargs)


def test_consumer_pair_forwarded():
    with patch("src.tender_research.rag.data_platform.DataPlatformClient") as constructor:
        build_data_platform_client(cfg(rag_data_platform_consumer="tender-agent",
                                       rag_data_platform_consumer_key="test-consumer"))
        assert constructor.call_args.kwargs["consumer"] == "tender-agent"
        assert constructor.call_args.kwargs["consumer_key"] == "test-consumer"


def test_incomplete_pair_fails_closed():
    with pytest.raises(ValueError, match="configured together"):
        build_data_platform_client(cfg(rag_data_platform_consumer="tender-agent"))


def test_legacy_client_without_consumer():
    with patch("src.tender_research.rag.data_platform.DataPlatformClient") as constructor:
        build_data_platform_client(cfg())
        assert "consumer" not in constructor.call_args.kwargs
