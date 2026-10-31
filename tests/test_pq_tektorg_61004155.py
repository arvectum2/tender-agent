"""Offline CAS and scope regression tests for source-bound UKRM enrichment."""
import copy

import pytest

from scripts.market_intelligence import enrich_pq_tektorg_61004155 as mod
from scripts.market_intelligence.enrich_pq_missing_field import digest


def test_model_names_and_scope():
    assert len(mod.MEMBERS) == 2
    assert all("УКРМ-6-1-" in name for name in mod.MEMBERS)
    assert mod.FIELDS["voltage_kv"] == "6"
    assert "450" in mod.FIELDS["power"] and "900" in mod.FIELDS["power"]
    assert "не сумма поставки" in mod.FIELDS["power"]


def fixture(monkeypatch):
    data = {"canonical_id": mod.CID, "procedure_id": "РН61004155",
            "scope": "supply", "customer": {"inn": "0277106840"},
            "quantity": None, "voltage_kv": None, "power": None}
    h = digest(data)
    monkeypatch.setattr(mod, "OLD", h)
    return {"id": mod.CID, "owner": "tender-agent", "rev": 2,
            "hash": h, "data": data, "meta": {}}


def test_validate_accepts_only_exact_old_null(monkeypatch):
    row = fixture(monkeypatch)
    mod.validate(row)
    for key, val in (("voltage_kv", "10"), ("power", "900 кВАр"),
                     ("quantity", 2)):
        bad = copy.deepcopy(row)
        bad["data"][key] = val
        with pytest.raises(RuntimeError, match="CAS"):
            mod.validate(bad)


def test_validate_rejects_owner_revision_and_identity(monkeypatch):
    row = fixture(monkeypatch)
    for key, val in (("owner", "someone-else"), ("rev", 3), ("id", "wrong")):
        bad = copy.deepcopy(row)
        bad[key] = val
        with pytest.raises(RuntimeError, match="CAS"):
            mod.validate(bad)
