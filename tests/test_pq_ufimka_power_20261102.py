"""Ufimka source-bound P2 field is null-only, not a paid equipment sale."""
import pytest

from scripts.market_intelligence.enrich_pq_missing_field import digest
from scripts.market_intelligence.enrich_pq_ufimka_power_20261102 import (
    CID,
    SHA,
    URL,
    VALUE,
    prepared,
    validate,
)


def sample():
    d = {"canonical_id": CID, "procedure_id": "32514476448", "scope": "epc",
         "equipment_voltage_kv": 10, "quantity": 2, "description": "БСК Уфимка",
         "evidence": []}
    return {"id": CID, "owner": "tender-agent", "rev": 3,
            "hash": digest(d), "data": d, "meta": {}}


def test_guarded_p2_enrichment_no_sale_attribution():
    row = sample()
    validate(row)
    data, meta, h = prepared(row, {"url": URL, "sha256": SHA})
    assert data["power"] == VALUE and h == digest(data)
    assert meta["ufimka_bsk_power_20261102"]["paid_sale_verified"] is False
    assert meta["ufimka_bsk_power_20261102"]["equipment_only_price_verified"] is False


@pytest.mark.parametrize("change", [
    {"power": "1 Мвар"}, {"quantity": 1}, {"equipment_voltage_kv": 110},
    {"scope": "supply"}, {"procedure_id": "32514476449"},
])
def test_fail_closed_on_conflicts(change):
    row = sample()
    data = {**row["data"], **change}
    with pytest.raises(RuntimeError):
        validate({**row, "data": data, "hash": digest(data)})
