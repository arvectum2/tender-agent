"""The corpus URL queue is bounded, reproducible and never an award assertion."""
import json

import pytest

from src.modules.market_intelligence.pq_etp_queue_expand import expand


def _corpus(path, records):
    path.write_text(json.dumps({"records": records}), encoding="utf-8")


def test_expand_source_urls_deduplicates_aliases_and_excludes_generic(tmp_path):
    leads = tmp_path / "leads.json"
    url = "https://synapsenet.ru/zakupki/b2b/4565274"
    _corpus(leads, [
        {"procedure_id": "4565274", "evidence": [
            {"url": url}, {"url": "https://zakupki.kontur.ru/category-region/foo"},
            {"url": "http://synapsenet.ru/unsafe"},
            {"url": "https://bad:secret@synapsenet.ru/secret"}]},
        {"procedure_id": "4565274-reissue", "source_url": url},
        {"canonical_id": "commercial:unknown:lot1",
         "sources": ["https://b2b.house/purchase/known"]},
    ])
    out = tmp_path / "queue.json"
    result = expand(leads_file=leads, output=out)
    assert result["unique_urls"] == 2
    data = json.loads(out.read_text())
    assert data["tasks"][0]["aliases"] == ["4565274", "4565274-reissue"]
    assert data["tasks"][1]["procedure_id"] == "commercial:unknown:lot1"
    assert data["skipped"] == {"unsafe_or_unsupported": 1,
                               "generic_index": 1, "missing_identity": 0}
    assert data["signed_contracts_verified"] is False
    assert data["original_documents_verified"] is False
    before = out.read_bytes()
    expand(leads_file=leads, output=out)
    assert out.read_bytes() == before


def test_expand_budget_fails_without_replacing_prior_queue(tmp_path):
    leads = tmp_path / "leads.json"
    _corpus(leads, [{"procedure_id": "A", "source_url":
                    "https://synapsenet.ru/zakupki/b2b/1"},
                   {"procedure_id": "B", "source_url":
                    "https://synapsenet.ru/zakupki/b2b/2"}])
    out = tmp_path / "queue.json"
    out.write_text("previous")
    with pytest.raises(ValueError, match="budget"):
        expand(leads_file=leads, output=out, max_urls=1)
    assert out.read_text() == "previous"


def test_expand_rejects_symlinks_and_malformed_records(tmp_path):
    leads = tmp_path / "leads.json"
    _corpus(leads, [None])
    with pytest.raises(TypeError, match="lead record"):
        expand(leads_file=leads, output=tmp_path / "queue.json")
    _corpus(leads, [])
    link = tmp_path / "alias.json"
    link.symlink_to(leads)
    with pytest.raises(ValueError, match="scope"):
        expand(leads_file=link, output=tmp_path / "queue.json")
