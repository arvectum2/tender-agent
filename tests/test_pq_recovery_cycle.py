import json
from pathlib import Path

import pytest

from src.modules.market_intelligence import pq_recovery_cycle as mod


def setup_inputs(tmp_path: Path):
    leads = tmp_path / "leads.json"
    leads.write_text(json.dumps({"records": [{"procedure_id": "32313008364"}]}))
    source = tmp_path / "originals"
    source.mkdir()
    ontology = tmp_path / "ontology.yaml"
    ontology.write_text("families: []")
    return leads, source, ontology


def stub_sources(monkeypatch):
    monkeypatch.setattr(mod, "inventory", lambda **kw: {
        "lead_count": 1, "output": str(kw["output"])})
    monkeypatch.setattr(mod, "seed", lambda **kw: {
        "source_root": str(kw["sources"]), "created": [], "existing": [],
        "skipped": [], "errors": []})


def test_manifest_only_fails_before_mutation(tmp_path):
    leads, source, ontology = setup_inputs(tmp_path)
    leads.write_text('{"total_active_rows":101}')
    with pytest.raises(ValueError, match="Materialized"):
        mod.cycle(leads_file=leads, source_roots=[source], ontology=ontology,
                  queue_dir=tmp_path / "queue", output_dir=tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_offline_cycle_records_unattempted_and_releases_lease(tmp_path, monkeypatch):
    leads, source, ontology = setup_inputs(tmp_path)
    stub_sources(monkeypatch)
    monkeypatch.setattr(mod, "next_packet", lambda **kw: {"status": "empty"})
    result = mod.cycle(leads_file=leads, source_roots=[source], ontology=ontology,
                       queue_dir=tmp_path / "queue", output_dir=tmp_path / "out")
    assert result["official_notice_search"]["status"] == "not_attempted"
    assert result["signed_contracts_verified_this_cycle"] == 0
    assert result["market_total_rub"] is None
    assert json.loads((tmp_path / "out/last_cycle.json").read_text()) == result
    assert not (tmp_path / "out/watchdog-mi-lease").exists()


def test_live_search_pending_packet(tmp_path, monkeypatch):
    leads, source, ontology = setup_inputs(tmp_path)
    stub_sources(monkeypatch)
    monkeypatch.setattr(mod, "source_search", lambda **kw: {
        "attempts_this_run": 1, "matched": 1})
    monkeypatch.setattr(mod, "next_packet", lambda **kw: {
        "status": "pending", "id": "32313008364-abc"})
    result = mod.cycle(leads_file=leads, source_roots=[source], ontology=ontology,
                       queue_dir=tmp_path / "queue", output_dir=tmp_path / "out",
                       live_search=True)
    assert result["official_notice_search"]["matched"] == 1
    assert result["pending_review"]["id"] == "32313008364-abc"
    assert "ChatGPT" in result["next_action"]


def test_held_lease_does_not_mutate(tmp_path):
    leads, source, ontology = setup_inputs(tmp_path)
    lease = mod.acquire(tmp_path / "out/watchdog-mi-lease")
    try:
        result = mod.cycle(leads_file=leads, source_roots=[source], ontology=ontology,
                           queue_dir=tmp_path / "queue", output_dir=tmp_path / "out")
        assert result["status"] == "lease_blocked"
        assert not (tmp_path / "out/last_cycle.json").exists()
    finally:
        assert mod.release(lease)
