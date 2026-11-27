import pytest

from scripts.market_intelligence.enrich_pq_argos_b2b_4559984 import (
    CID,
    SOURCES,
    prepared,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def sample():
    d = {"canonical_id": CID, "procedure_id": "4559984",
         "scope": "mixed_MTR_market_sounding_with_PQ_component",
         "equipment_model": "АУКРМ-6,3-1350-450-12 УХЛ4",
         "quantity": 1, "equipment_voltage_kv": 6.3,
         "customer": {"inn": "8608063577"},
         "evidence": [{"url": "https://synapsenet.ru/zakupki/b2b/4559984--example"}]}
    return {"id": CID, "owner": "tender-agent", "hash": digest(d),
            "rev": 1, "meta": {}, "data": d}


def test_null_only_original_upgrade():
    row = sample()
    validate(row)
    sources = [{"url": u, "sha256": sha} for _, sha, u in SOURCES]
    data, meta, new_hash = prepared(row, sources)
    assert len(data["source_urls"]) == 2
    assert data["source_urls"][1]["sha"] == SOURCES[1][1]
    assert new_hash == digest(data)
    assert meta["argos_b2b_original_20261102"]["signed_supplier_verified"] is False
    assert data["equipment_voltage_kv"] == 6.3


@pytest.mark.parametrize("field,value", [
    ("source_urls", []), ("quantity", 2), ("equipment_voltage_kv", 35),
    ("scope", "signed_equipment_supply"), ("equipment_model", "UNKNOWN"),
])
def test_conflict_blocks(field, value):
    row = sample()
    row["data"][field] = value
    row["hash"] = digest(row["data"])
    with pytest.raises(RuntimeError):
        validate(row)


def test_hash_drift_blocks():
    row = sample()
    row["hash"] = "0" * 64
    with pytest.raises(RuntimeError):
        validate(row)
