"""Agent safety, deterministic discovery and bounded resume."""
from datetime import date

import pytest

from src.modules.market_intelligence.pq_research_agent import run_agent


def test_unverified_source_never_fetches(tmp_path):
    calls = []
    result = run_agent(source_root=tmp_path / "sources", output=tmp_path / "out",
                       day=date(2024, 4, 15), region="77", execute=True,
                       downloader=lambda **kw: calls.append(kw))
    assert result["status"] == "source_not_verified"
    assert calls == []


def test_reject_unsafe_scope(tmp_path):
    with pytest.raises(ValueError):
        run_agent(source_root=tmp_path, output=tmp_path / "out",
                  day=date(2024, 4, 15), region="xx")
    with pytest.raises(ValueError):
        run_agent(source_root=tmp_path, output=tmp_path / "out",
                  day=date(2024, 4, 15), region="77", max_notices=21)
