import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_month_discovery import _window, run


class Provider:
    def __init__(self, wrong=False):
        self.calls = 0
        self.wrong = wrong

    def search(self, *, query, date_from, date_to, page, page_size):
        from urllib.parse import urlencode
        self.calls += 1
        params = {"fz44" if self.wrong else "fz223": "on",
                  "pageNumber": "1", "searchString": query,
                  "publishDateFrom": date_from.strftime("%d.%m.%Y"),
                  "publishDateTo": date_to.strftime("%d.%m.%Y")}
        url = "https://zakupki.gov.ru/epz/order/extendedsearch/results.html?" + urlencode(params)
        item = type("Item", (), {"registry_number": "32514720691",
                                  "publication_date": datetime(2025, 5, 12, tzinfo=UTC)})
        return type("Page", (), {"source_url": url, "status": "success",
                                  "items": [item], "has_next": False})


def test_month_scope_and_cooldown(tmp_path: Path):
    p = Provider()
    journal = tmp_path / "journal.json"
    kwargs = {"journal": journal, "months": ["2025-05"], "laws": ["223fz"],
              "queries": ["УКРМ"], "providers": {"223fz": p},
              "now": datetime(2026, 10, 28, tzinfo=UTC)}
    first = run(**kwargs)
    assert first["requests_this_run"] == 1
    assert first["date_bound_responses"] == 1
    assert first["coverage_exhaustive"] is False
    assert run(**kwargs)["requests_this_run"] == 0
    assert p.calls == 1
    event = json.loads(journal.read_text())["attempts"][0]
    assert event["candidates"][0]["date_in_window"]
    assert event["candidates"][0]["pq_relevance_verified"] is False
    assert event["signed_contract_verified"] is False


def test_mismatched_law_fails_source_binding(tmp_path: Path):
    result = run(journal=tmp_path / "j.json", months=["2025-05"],
                 laws=["223fz"], queries=["УКРМ"],
                 providers={"223fz": Provider(wrong=True)})
    assert result["date_bound_responses"] == 0
    assert result["statuses"] == {"provider_error": 1}


def test_malformed_journal_fails_closed(tmp_path: Path):
    journal = tmp_path / "j.json"
    journal.write_text(json.dumps({"schema_version": "pq-month-scoped-eis/1",
                                   "attempts": [{"law": "223fz", "month": "2025-05",
                                                 "query": "УКРМ",
                                                 "timestamp": "2099-01-01T00:00:00+00:00"}]}))
    with pytest.raises(ValueError, match="fail closed"):
        run(journal=journal, months=["2025-05"], laws=["223fz"],
            queries=["УКРМ"], providers={"223fz": Provider()},
            now=datetime(2026, 10, 28, tzinfo=UTC))


@pytest.mark.parametrize("month", ["2023-12", "2027-01", "2025-13", "2025-2", "oops"])
def test_invalid_month(month):
    with pytest.raises(ValueError):
        _window(month)


def test_bounded_budget(tmp_path: Path):
    with pytest.raises(ValueError, match="Unbounded"):
        run(journal=tmp_path / "j.json", months=["2024-01"],
            laws=["223fz"], queries=["УКРМ"], max_requests=100)
