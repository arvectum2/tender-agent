"""Registered contract six-line item split, with no inferred equipment sale."""
from copy import deepcopy

import pytest

from scripts.market_intelligence.enrich_pq_missing_field import digest
from scripts.market_intelligence.enrich_pq_rosseti_south_items_20261103 import (
    CID,
    KEY,
    REG,
    SHA,
    make_fields,
    prepare,
    validate,
)


def row():
    d = {"canonical_id": CID, "procedure_id": "32616339168",
         "customer": {"inn": "4716016979"}, "contract_registry_number": REG,
         "contract_number": "312", "contract_registered_price_rub": "4350000.00",
         "quantity": 24, "registered_signed_contract_verified": True,
         "supplier_verified": False, "pq_equipment_only_contract_rub": None,
         "evidence": [], "scope": "supply_components", "equipment_voltage_kv": None}
    return {"id": CID, "owner": "tender-agent", "data": d,
            "hash": digest(d), "rev": 3, "meta": {}}


def test_split_and_scope():
    r = row()
    validate(r)
    source = {"url": "https://zakupki.gov.ru", "sha256": SHA, "excerpt": "original"}
    data, meta, sha = prepare(r, source)
    assert sum(x["quantity"] for x in make_fields()["contract_capacitor_item_lines"]) == 24
    assert data["contract_capacitor_nominal_6plus_kv_rub"] == "3270000.02"
    assert data["contract_capacitor_nominal_below_6kv_rub"] == "1080000.02"
    assert data["contract_capacitor_item_rounding_delta_rub"] == "0.04"
    assert data["equipment_voltage_kv"] is None
    assert data["pq_equipment_only_contract_rub"] is None
    assert data["supplier_verified"] is False
    assert meta[KEY]["network_6_35kv_verified"] is False
    assert sha == digest(data)


@pytest.mark.parametrize("key,value", [
    ("contract_capacitor_item_lines", []),
    ("quantity", 25), ("contract_registry_number", "bad"),
    ("supplier_verified", True), ("pq_equipment_only_contract_rub", "3270000.02"),
])
def test_conflicts(key, value):
    r = deepcopy(row())
    r["data"][key] = value
    r["hash"] = digest(r["data"])
    with pytest.raises(RuntimeError, match="CAS conflict"):
        validate(r)


def test_hash_owner_and_metadata():
    r = row()
    r["hash"] = "0" * 64
    with pytest.raises(RuntimeError):
        validate(r)
    r = row()
    r["owner"] = "other"
    with pytest.raises(RuntimeError):
        validate(r)
    r = row()
    r["meta"][KEY] = {"already": True}
    with pytest.raises(RuntimeError):
        validate(r)
