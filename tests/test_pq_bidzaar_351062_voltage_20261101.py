"""Pure null-only CAS tests; no private runtime or database required."""
import pytest

from scripts.market_intelligence.enrich_pq_bidzaar_351062_voltage import (
    CARD_URL,
    CID,
    DOC_SHA,
    VALUE,
    updated,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def sample():
    data = {
        "canonical_id": CID, "procedure_id": "351-062", "scope": "supply",
        "quantity": 2, "power": "3000 кВАр (по опросному листу; не умножать на 2)",
        "equipment_voltage_kv": None, "voltage_kv": None,
        "evidence": [{"url": CARD_URL, "sha256": "card"}],
    }
    return {"id": CID, "owner": "tender-agent", "data": data,
            "hash": digest(data), "rev": 3, "meta": {"bidzaar_351062_p2": {}}}


def test_source_bound_voltage_only():
    row = sample()
    validate(row)
    data, meta = updated(row)
    assert data["equipment_voltage_kv"] == VALUE == "6.3"
    assert data["quantity"] == 2 and data["power"] == row["data"]["power"]
    assert meta["bidzaar_351062_voltage"]["original_sha256"] == DOC_SHA
    assert row["data"]["equipment_voltage_kv"] is None


@pytest.mark.parametrize(("field", "value"), [
    ("equipment_voltage_kv", "10"), ("voltage_kv", "6"), ("quantity", 3),
    ("scope", "service"), ("power", "6000 кВАр"),
])
def test_conflicting_fields_blocked(field, value):
    row = sample()
    row["data"][field] = value
    row["hash"] = digest(row["data"])
    with pytest.raises(RuntimeError):
        validate(row)


def test_owner_and_source_guard():
    row = sample()
    row["owner"] = "other"
    with pytest.raises(RuntimeError):
        validate(row)
    row = sample()
    row["data"]["evidence"] = []
    row["hash"] = digest(row["data"])
    with pytest.raises(RuntimeError):
        validate(row)
