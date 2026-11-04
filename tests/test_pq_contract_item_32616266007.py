"""Guarded signed contract item: no tender-TZ overwrite or supplier inference."""
from copy import deepcopy

import pytest

from scripts.market_intelligence.enrich_pq_eis_contract_item_32616266007 import (
    CID,
    FIELDS,
    prepare,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def row():
    data = {
        "canonical_id": CID, "procedure_id": "32616266007",
        "scope": "capacitor_component_supply_spares",
        "customer": {"inn": "4716016979"},
        "contract_registry_number": "54716016979260041190000",
        "contract_number": "1605245", "contract_registered_price_rub": "662460.00",
        "quantity": 5, "technical": {"type": "QBANK-A CHDB-142 or equivalent"},
        "signed_supplier_verified": False, "paid_verified": False, "evidence": [],
    }
    return {"id": CID, "owner": "tender-agent", "data": data,
            "meta": {}, "hash": digest(data), "rev": 3}


def test_contract_item_enrichment_preserves_tender_spec_and_unknown_supplier():
    before = row()
    validate(before)
    new_data, new_meta, new_hash = prepare(before, [{"url": "official", "sha256": "a"*64,
                                                      "excerpt": "item"}])
    assert all(new_data[k] == v for k, v in FIELDS.items())
    assert new_data["technical"] == before["data"]["technical"]
    assert new_data["signed_supplier_verified"] is False
    assert new_data["paid_verified"] is False
    assert new_meta["eis_20261101_contract_item_enrichment"]["previous_hash"] == before["hash"]
    assert new_hash == digest(new_data)


def test_rejects_conflicting_existing_field_and_signed_supplier():
    original = row()
    for key, value in [("contract_item_model", "different"), ("signed_supplier_verified", True)]:
        conflicting = deepcopy(original)
        conflicting["data"][key] = value
        conflicting["hash"] = digest(conflicting["data"])
        with pytest.raises(RuntimeError, match="CAS conflict"):
            validate(conflicting)


def test_client_report_source_bound_note_requires_exact_sha():
    from scripts.market_intelligence.enrich_pq_eis_contract_item_32616266007 import (
        SOURCE,
    )
    from scripts.market_intelligence.export_fgi_deck_snapshot import (
        source_bound_eis_contract_item_note,
    )
    data = {**row()["data"], **FIELDS}
    metadata = {"eis_20261101_contract_item_enrichment": {
        "sources": [{"url": x[2], "sha256": x[1]} for x in SOURCE]}}
    note = source_bound_eis_contract_item_note(data, metadata)
    assert "КЭПФ-12-450-2" in note
    assert "не подтверждены" in note
    assert "не поставка полноценной системы" in note
    metadata["eis_20261101_contract_item_enrichment"]["sources"][0]["sha256"] = "0" * 64
    assert source_bound_eis_contract_item_note(data, metadata) is None
