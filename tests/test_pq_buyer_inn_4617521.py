"""Fail-closed checks for the first-party B2B buyer INN field."""
import copy

import pytest

from scripts.market_intelligence import enrich_pq_buyer_inn_4617521 as mod
from scripts.market_intelligence.enrich_pq_missing_field import digest


def row():
    data = {
        "canonical_id": mod.CID,
        "procedure_id": "4617521",
        "scope": "mixed_supply_install_pnr",
        "evidence": [{"url": mod.URL, "sha256": mod.SHA}],
    }
    return {"id": mod.CID, "owner": "tender-agent", "hash": digest(data),
            "rev": 1, "data": data, "meta": {}}


def test_buyer_inn_validation_accepts_exact_null_bound_source():
    mod.validate(row())


@pytest.mark.parametrize("change", ["wrong_owner", "existing_inn", "wrong_sha", "wrong_scope"])
def test_buyer_inn_validation_rejects_conflict(change):
    r = row()
    if change == "wrong_owner":
        r["owner"] = "other"
    elif change == "existing_inn":
        r["data"]["buyer_inn"] = "0000000000"
        r["hash"] = digest(r["data"])
    elif change == "wrong_sha":
        r["data"]["evidence"][0]["sha256"] = "0" * 64
        r["hash"] = digest(r["data"])
    elif change == "wrong_scope":
        r["data"]["scope"] = "different"
        r["hash"] = digest(r["data"])
    with pytest.raises(RuntimeError, match="blocked"):
        mod.validate(r)


def test_buyer_inn_update_uses_cas_and_preserves_lot_count(monkeypatch):
    original = row()
    updated = copy.deepcopy(original)
    updated["data"]["buyer_inn"] = mod.INN
    updated["hash"] = digest(updated["data"])
    updated["rev"] = 2
    queries = []
    monkeypatch.setattr(mod, "psql", lambda sql: queries.append(sql))
    monkeypatch.setattr(mod, "snapshot", lambda: {"rows": 117, "unique": 117, "records": 117})
    monkeypatch.setattr(mod, "get_row", lambda cid: updated)
    result = mod.update(original, {"rows": 117, "unique": 117, "records": 117}, {"sha256": mod.SHA})
    assert result["new_verified_fields"] == 1
    assert "SERIALIZABLE" in queries[0]
    assert "d.revision=1" in queries[0]
    assert "(d.data->'buyer_inn') IS NULL" in queries[0]
    assert "content_hash" in queries[0]
