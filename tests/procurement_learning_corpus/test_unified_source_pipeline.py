"""Offline strict source discovery and canonical queued-candidate semantics."""
from __future__ import annotations

import copy
import json
from datetime import UTC, datetime

import pytest

from scripts.procurement_llm import unified_source_pipeline as u

DATE = datetime(2026, 10, 18, 20, 15, tzinfo=UTC)
W1 = "https://workspace.ru/tenders/razrabotka-korporativnogo-sayta-19043/"
W2 = "https://workspace.ru/tenders/dizayn-etiketki-19045/"
W3 = "https://workspace.ru/tenders/vnedrenie-sistemy-avtomatizacii-19099/"
B1 = "https://www.b2b-center.ru/app/market-next/razrabotka-novogo-saita/tender-4643484/"
B2 = "https://www.b2b-center.ru/market/vnedrenie-crm-sistemy/tender-4633713/"
E1 = "0163200000326005243"


def policy():
    return {
        "schema": "arvectum_source_pipeline_v1",
        "b2b_categories": ["razrabotka-sajtov", "crm-sistemy"],
        "max_index_items": 10,
        "max_market_new_per_run": 3,
        "max_existing_refresh": 1,
        "eis_known_numbers_refresh": [E1],
        "fail_if_source_unavailable": False,
        "eis_public_44fz_discovery_enabled": True,
        "eis_public_days_back": 3,
        "eis_public_sample_limit": 30,
        "eis_public_new_max": 2,
    }


def rss(*, duplicate=False):
    def item(link, title):
        return f"<item><title>{title}</title><link>{link}</link></item>"
    raw = ("<?xml version='1.0'?><rss version='2.0'><channel>"
           + item(W1, "Разработка корпоративного сайта")
           + item(W2, "Дизайн этикетки косметики")
           + item(W3, "Внедрение системы автоматизации учёта")
           + (item(W1, "Разработка сайта дубль") if duplicate else "")
           + "</channel></rss>")
    return raw.encode()


def index_for(category):
    links = [B1] if category == "razrabotka-sajtov" else [B2]
    return ("<html><body><h1>Веб-разработка</h1>"
            + "".join(f'<a href="{x}">Оригинал</a>' for x in links)
            + ("x" * 180) + "</body></html>").encode()


def fake_eis_public(*, days_back, sample_limit):
    assert 1 <= days_back <= 7 and 1 <= sample_limit <= 40
    return [], {
        "source": "eis_external_public_44fz", "status": "OK",
        "sampled_listings": 4, "it_title_heuristic_matches": 0,
        "sampling_not_full_eis_registry": True,
    }


def fake_index(url):
    if url == u.WORKSPACE_RSS:
        return rss(), "text/xml"
    if "razrabotka-sajtov/" in url:
        return index_for("razrabotka-sajtov"), "text/html"
    if "crm-sistemy/" in url:
        return index_for("crm-sistemy"), "text/html"
    raise AssertionError("source allowlist violated")


def test_exact_real_policy_and_only_allowlisted_index():
    config = u.load_policy(u.POLICY)
    assert config["max_market_new_per_run"] <= 8
    assert len(config["eis_known_numbers_refresh"]) == 3
    assert config["eis_public_44fz_discovery_enabled"] is True
    with pytest.raises(u.PipelineError):
        u.read_index("https://outside.example/collector")


def test_workspace_rss_it_titles_and_duplicate_identity():
    found = u.parse_workspace_rss(rss(), max_items=10)
    assert [x["id"] for x in found] == ["19043", "19099"]
    with pytest.raises(u.PipelineError, match="duplicate"):
        u.parse_workspace_rss(rss(duplicate=True), max_items=10)


def test_b2b_source_url_exact_and_correct_ids():
    found = u.parse_b2b_index(index_for("razrabotka-sajtov"), max_items=5)
    assert len(found) == 1 and found[0]["id"] == "4643484"
    assert found[0]["platform"] == "b2bcenter"


@pytest.mark.parametrize("change", [
    lambda p: p.update(schema="unknown"),
    lambda p: p.update(max_market_new_per_run=999),
    lambda p: p.update(max_existing_refresh=-1),
    lambda p: p.update(max_market_new_per_run=True),
    lambda p: p.update(b2b_categories=["unknown"]),
    lambda p: p.update(b2b_categories=["crm-sistemy", "crm-sistemy"]),
    lambda p: p.update(eis_known_numbers_refresh=["unknown"]),
    lambda p: p.update(fail_if_source_unavailable="false"),
    lambda p: p.update(eis_public_sample_limit=200),
    lambda p: p.update(eis_public_days_back=0),
    lambda p: p.update(eis_public_44fz_discovery_enabled="true"),
])
def test_unbounded_or_unsafe_policy_rejected(change):
    p = policy()
    change(p)
    with pytest.raises((u.PipelineError, ValueError)):
        u.validate_policy(p)


def test_three_independent_indexes_and_bounded_known_refresh():
    cards, details = u.discover(policy(), read=fake_index)
    assert [x["id"] for x in cards] == ["19043", "19099", "4643484", "4633713"]
    assert all(x["status"] == "OK" for x in details["indexes"])
    selected = u.plan(cards, known={"workspace:19043", "b2bcenter:4633713"},
                      analyzed={"workspace:19043"}, max_new=2, max_refresh=1)
    assert selected["fresh_source_refs"] == ["workspace:19099", "b2bcenter:4643484"]
    assert selected["recheck_source_refs"] == ["workspace:19043"]
    assert selected["needs_analysis"] == ["workspace:19099", "b2bcenter:4643484"]


def test_missing_workspace_index_not_fake_empty_result():
    def bad(url):
        if url == u.WORKSPACE_RSS:
            raise TimeoutError("source unavailable")
        return fake_index(url)
    candidates, evidence = u.discover(policy(), read=bad)
    assert len(candidates) == 2
    assert evidence["indexes"][0]["status"] == "UNAVAILABLE_OR_AMBIGUOUS"
    strict = policy()
    strict["fail_if_source_unavailable"] = True
    with pytest.raises(u.PipelineError):
        u.discover(strict, read=bad)


def test_source_index_mime_rejected():
    def bad(url):
        if url == u.WORKSPACE_RSS:
            return rss(), "text/html"
        return fake_index(url)
    _, details = u.discover(policy(), read=bad)
    assert details["indexes"][0]["status"] == "UNAVAILABLE_OR_AMBIGUOUS"


def test_bad_xml_entity_and_wrong_rss_root_rejected():
    with pytest.raises(u.PipelineError):
        u.parse_workspace_rss(b'<!DOCTYPE rss [<!ENTITY s "secret">]>' + rss(), max_items=10)
    with pytest.raises(u.PipelineError):
        u.parse_workspace_rss(b"<html>" + b"x" * 200 + b"</html>", max_items=10)


def test_readonly_discovery_attestation_and_pending_not_actual_analysis(monkeypatch):
    initial = copy.deepcopy(policy())
    calls = []
    def market_collect(cards, **kwargs):
        assert kwargs["apply"] is False
        calls.append(("market", cards[0]["id"]))
        return {"sources": 1, "database_mutations": 0}
    def eis_collect(numbers, **kwargs):
        assert kwargs["apply"] is False
        calls.append(("eis", numbers[0]))
        return {"official_archives_verified": 1, "db_mutations": 0}
    monkeypatch.setattr(u.market, "collect", market_collect)
    monkeypatch.setattr(u.eis, "collect", eis_collect)
    result = u.run(policy(), index_read=fake_index,
                   eis_public_search=fake_eis_public,
                   known={"workspace:19043"}, analyzed={"workspace:19043"},
                   apply=False, observed=DATE)
    assert policy() == initial
    assert result["new_learning_source_observations"] == 0
    assert result["successful_original_count"] == 5
    assert len(calls) == 5
    assert result["independent_chatgpt_evaluation_performed"] is False
    assert result["independent_tender_agent_evaluation_performed"] is False
    assert result["pending_actual_tender_agent_analysis"] == []
    assert "workspace:19099" in result["would_queue_if_captured"]
    assert result["all_eis_new_procurements_autodiscovery"] is False
    assert result["training_gold_created"] is False


def test_apply_requires_prewrite_backup_and_no_partial_mutations(monkeypatch):
    calls = []
    monkeypatch.setattr(u.market, "collect", lambda *a, **kw: calls.append(a))
    with pytest.raises(u.PipelineError, match="backup required"):
        u.run(policy(), index_read=fake_index,
                   eis_public_search=fake_eis_public, apply=True, backup_verified=False)
    assert calls == []


def test_true_canonical_source_capture_queue_and_no_legal_go(monkeypatch):
    def market_collect(cards, **kwargs):
        assert kwargs["apply"] is True
        return {"inserted": 1, "existing": 0}
    def eis_collect(numbers, **kwargs):
        assert kwargs["apply"] is True
        return {"inserted": 0, "existing": 1}
    monkeypatch.setattr(u.market, "collect", market_collect)
    monkeypatch.setattr(u.eis, "collect", eis_collect)
    result = u.run(policy(), index_read=fake_index,
                   eis_public_search=fake_eis_public,
                   known={"workspace:19043"}, analyzed=set(),
                   apply=True, backup_verified=True, observed=DATE)
    assert result["new_learning_source_observations"] == 4
    assert "workspace:19043" in result["pending_actual_tender_agent_analysis"]
    assert E1 in result["pending_actual_tender_agent_analysis"]
    assert result["fully_qualified_bid_go"] == 0
    assert result["training_gold_created"] is False


def test_failed_original_preserves_other_sources_but_fails_cycle(monkeypatch):
    def market_collect(cards, **kwargs):
        if cards[0]["platform"] == "b2bcenter":
            raise TimeoutError("unavailable")
        return {"inserted": 1}
    monkeypatch.setattr(u.market, "collect", market_collect)
    monkeypatch.setattr(u.eis, "collect", lambda *a, **k: {"inserted": 0})
    result = u.run(policy(), index_read=fake_index,
                   eis_public_search=fake_eis_public, apply=True,
                   backup_verified=True, observed=DATE)
    assert result["failures"] and not result["all_requested_originals_captured"]
    assert all("reason_class" in failure for failure in result["failures"])
    assert "unavailable" not in json.dumps(result)


def test_replayed_existing_sources_still_pending_for_actual_analysis(monkeypatch):
    monkeypatch.setattr(u.market, "collect", lambda *a, **k: {"inserted": 0, "existing": 1})
    monkeypatch.setattr(u.eis, "collect", lambda *a, **k: {"inserted": 0, "existing": 1})
    refs = {"workspace:19043", "workspace:19099", "b2bcenter:4643484",
            "b2bcenter:4633713", E1}
    result = u.run(policy(), index_read=fake_index,
                   eis_public_search=fake_eis_public, known=refs,
                   analyzed={"workspace:19043", E1},
                   apply=True, backup_verified=True, observed=DATE)
    assert "workspace:19043" not in result["pending_actual_tender_agent_analysis"]
    assert E1 not in result["pending_actual_tender_agent_analysis"]
    assert "workspace:19099" in result["pending_actual_tender_agent_analysis"]
    assert result["new_learning_source_observations"] == 0


def test_large_workspace_rss_cannot_starve_b2b_index_results():
    flooded = [
        {"platform": "workspace", "id": str(19000 + i),
         "url": f"https://workspace.ru/tenders/razrabotka-sayta-{19000 + i}/"}
        for i in range(24)
    ]
    flooded.extend([
        {"platform": "b2bcenter", "id": "4643484", "url": B1},
        {"platform": "b2bcenter", "id": "4633713", "url": B2},
    ])
    picked = u.plan(
        flooded, known=set(), analyzed=set(), max_new=5, max_refresh=0
    )
    assert len(picked["fresh_source_refs"]) == 5
    assert picked["fresh_source_refs"][0].startswith("workspace:")
    assert picked["fresh_source_refs"][1].startswith("b2bcenter:")
    assert sum(x.startswith("b2bcenter:") for x in picked["fresh_source_refs"]) == 2


def test_public_44fz_real_source_type_title_heuristic_and_demo_excluded(monkeypatch):
    from types import SimpleNamespace

    from src.tender_research.registry_discovery import SourceType

    rows = [
        SimpleNamespace(
            registry_number="0163200000326005243",
            tender_title="Разработка программного обеспечения сайта",
        ),
        SimpleNamespace(
            registry_number="0332100025426000039",
            tender_title="Образовательная программа повышения квалификации",
        ),
        SimpleNamespace(
            registry_number="0148200002426000013",
            tender_title="Внедрение CRM системы",
        ),
    ]

    class FakeDiscovery:
        def __init__(self, config):
            self.config = config

        def discover(self, **args):
            assert args["source"] == "external_public_44fz"
            assert args["days_back"] == 3
            return SimpleNamespace(
                numbers=rows, network_status="success", is_demo=False,
                selected_source_type=SourceType.EXTERNAL_PUBLIC_44FZ,
            )

    monkeypatch.setattr(u, "RegistryNumberDiscovery", FakeDiscovery)
    numbers, provenance = u.discover_public_eis_numbers(
        days_back=3, sample_limit=30
    )
    assert numbers == ["0163200000326005243", "0148200002426000013"]
    assert provenance["sampling_not_full_eis_registry"] is True
    assert provenance["demo_or_seed_data_accepted"] is False


def test_public_eis_demo_or_error_cannot_be_reported_as_ordinary_empty(monkeypatch):
    from types import SimpleNamespace

    from src.tender_research.registry_discovery import SourceType

    class FakeDiscovery:
        def __init__(self, config):
            pass

        def discover(self, **kwargs):
            return SimpleNamespace(
                numbers=[], network_status="success", is_demo=True,
                selected_source_type=SourceType.EXTERNAL_PUBLIC_44FZ,
            )

    monkeypatch.setattr(u, "RegistryNumberDiscovery", FakeDiscovery)
    with pytest.raises(u.PipelineError, match="unavailable"):
        u.discover_public_eis_numbers(days_back=3, sample_limit=10)


def test_new_public_eis_number_needs_official_original_before_queue(monkeypatch):
    extra = "0372200172326000015"
    def real_source(**_):
        return [extra], {
            "source": "eis_external_public_44fz", "status": "OK",
            "sampled_listings": 30, "it_title_heuristic_matches": 1,
            "sampling_not_full_eis_registry": True,
        }

    def collect_market(cards, **kw):
        return {"inserted": 0, "existing": 1}

    seen = []
    def collect_eis(numbers, **kw):
        seen.append(numbers[0])
        return {"inserted": 1, "existing": 0}

    monkeypatch.setattr(u.market, "collect", collect_market)
    monkeypatch.setattr(u.eis, "collect", collect_eis)
    result = u.run(
        policy(), index_read=fake_index, eis_public_search=real_source,
        apply=True, backup_verified=True, observed=DATE,
    )
    assert extra in seen
    assert result["selection"]["eis_new_public_title_heuristic_selected"] == 1
    assert extra in result["pending_actual_tender_agent_analysis"]
    assert result["all_eis_new_procurements_autodiscovery"] is False
    assert result["training_gold_created"] is False


def test_public_eis_search_down_is_explicit_failed_stage_and_no_fake_go(monkeypatch):
    def unavailable(**_):
        raise TimeoutError("original public search unavailable")

    monkeypatch.setattr(u.market, "collect", lambda *a, **k: {"inserted": 0})
    monkeypatch.setattr(u.eis, "collect", lambda *a, **k: {"inserted": 0})
    output = u.run(
        policy(), index_read=fake_index, eis_public_search=unavailable,
        apply=True, backup_verified=True, observed=DATE,
    )
    assert output["discovery"]["eis_public"]["status"] == "UNAVAILABLE_OR_AMBIGUOUS"
    assert output["all_requested_originals_captured"] is False
    assert output["fully_qualified_bid_go"] == 0
