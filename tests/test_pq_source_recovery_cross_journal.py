"""Official EIS exact-ID cooldown is shared across append-only journals."""
import json
from datetime import UTC, datetime

import pytest

from src.modules.market_intelligence import pq_source_recovery as recovery


class _Provider:
    def __init__(self):
        self.calls = []

    def search(self, *, query, page_size):
        self.calls.append(query)
        return type("Page", (), {"status": "empty", "items": [], "error": None})()


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_prior_exact_id_skipped_but_independent_case_runs(tmp_path, monkeypatch):
    provider = _Provider()
    provider.calls = []
    monkeypatch.setattr(recovery, "Public223FzSearchProvider", lambda: provider)
    monkeypatch.setattr(recovery, "Public44FzSearchProvider", lambda: provider)
    gaps = tmp_path / "gaps.json"
    _write(gaps, {"cases": [{"procedure_id": "32514720691"},
                            {"procedure_id": "32514754857"}]})
    prior = tmp_path / "prior.json"
    _write(prior, {"attempts": [{"query": "32514720691",
                               "timestamp": datetime.now(UTC).isoformat(),
                               "status": "success"}]})
    result = recovery.run(gaps=gaps, journal=tmp_path / "new.json",
                          prior_journals=[prior], max_cases=2)
    assert result["attempts_this_run"] == 1
    assert provider.calls == ["32514754857"]


def test_unreadable_timestamp_fails_closed_per_case(tmp_path, monkeypatch):
    provider = _Provider()
    provider.calls = []
    monkeypatch.setattr(recovery, "Public223FzSearchProvider", lambda: provider)
    monkeypatch.setattr(recovery, "Public44FzSearchProvider", lambda: provider)
    gaps = tmp_path / "gaps.json"
    _write(gaps, {"cases": [{"procedure_id": "32514720691"},
                            {"procedure_id": "32514754857"}]})
    prior = tmp_path / "prior.json"
    _write(prior, {"attempts": [{"procedure_id": "32514720691",
                               "timestamp": "unparseable"}]})
    result = recovery.run(gaps=gaps, journal=tmp_path / "new.json",
                          prior_journals=[prior])
    assert result["attempts_this_run"] == 1
    assert provider.calls == ["32514754857"]


def test_corrupt_prior_journal_blocks_all_network(tmp_path, monkeypatch):
    provider = _Provider()
    provider.calls = []
    monkeypatch.setattr(recovery, "Public223FzSearchProvider", lambda: provider)
    monkeypatch.setattr(recovery, "Public44FzSearchProvider", lambda: provider)
    gaps = tmp_path / "gaps.json"
    _write(gaps, {"cases": [{"procedure_id": "32514720691"}]})
    prior = tmp_path / "prior.json"
    prior.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError):
        recovery.run(gaps=gaps, journal=tmp_path / "new.json",
                     prior_journals=[prior])
    assert provider.calls == []
    assert not (tmp_path / "new.json").exists()
