"""Contract item model/quantity price source-bound null-only guards."""
from copy import deepcopy

import pytest

from scripts.market_intelligence.enrich_pq_kuzbass_filter_items_20261102 import (
    CID,
    FIELDS,
    SOURCE,
    prepare,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def row():
    d = {
        "canonical_id": CID, "procedure_id": "32514947144",
        "scope": "supply_components", "customer": {"inn": "4716016979"},
        "contract_registry_number": "54716016979250029010000",
        "contract_number": "1423177", "contract_registered_price_rub": "3158400.00",
        "quantity": 14, "pq_equipment_only_contract_rub": "3158400.00",
        "contract_signatory": None, "registered_signed_contract_verified": True,
        "technical": {"purpose": "spare capacitor components"}, "evidence": [],
    }
    return {"id": CID, "owner": "tender-agent", "data": d,
            "meta": {}, "hash": digest(d), "rev": 5}


def test_prepare_keeps_scope_supplier_and_original_technical():
    old = row()
    validate(old)
    sources = [{"url": x[2], "sha256": x[1], "excerpt": "original"} for x in SOURCE]
    new, meta, sha = prepare(old, sources)
    assert all(new[k] == v for k, v in FIELDS.items())
    assert new["technical"] == old["data"]["technical"]
    assert new["contract_signatory"] is None
    assert new["pq_equipment_only_contract_rub"] == "3158400.00"
    assert new["evidence"][-1]["sha256"] == SOURCE[0][1]
    assert meta["eis_kuzbass_filter_items_20261102"]["signed_supplier_verified"] is False
    assert sha == digest(new)


@pytest.mark.parametrize("key,value", [
    ("contract_item_model", "other"),
    ("quantity", 15),
    ("contract_signatory", "unverified"),
    ("scope", "epc"),
    ("pq_equipment_only_contract_rub", "0"),
])
def test_conflicting_fields_rejected(key, value):
    original = row()
    conflicting = deepcopy(original)
    conflicting["data"][key] = value
    conflicting["hash"] = digest(conflicting["data"])
    with pytest.raises(RuntimeError, match="CAS conflict"):
        validate(conflicting)


def test_content_hash_and_metadata_conflicts():
    r = row()
    r["hash"] = "0" * 64
    with pytest.raises(RuntimeError):
        validate(r)
    r = row()
    r["meta"]["eis_kuzbass_filter_items_20261102"] = {"already": True}
    with pytest.raises(RuntimeError):
        validate(r)


def test_client_note_country_requires_exact_sha_and_original_case_proof():
    from scripts.market_intelligence.export_fgi_deck_snapshot import (
        source_bound_filter_signed_note,
        verified_kuzbass_filter_items,
    )

    r = row()
    d, meta, _ = prepare(r, [{"url": SOURCE[0][2], "sha256": SOURCE[0][1], "excerpt": "original"}])
    meta["eis_contract_enrichment"] = {
        "role": "signed_completed_12kv_capacitor_components_for_500kv_substation",
        "supplier_verified": False, "payment_verified": False,
        "sources": [{"sha256": sha} for sha in (
            "66134a163aa0327c095ca0d68d691a597190d2d993c67dbf3cdb4fddc390d234",
            "ed1399c65155df6f9728e7a2ded84257d175663ae21830110a14e5b2753e6233",
            "bd23d3b1f01add4850de79eb46d20ef04f9cf51a7e28a43e39c24d5948c71d63",
        )],
    }
    d["contract_execution_completed"] = True
    assert verified_kuzbass_filter_items(d, meta)
    assert "страна происхождения" in source_bound_filter_signed_note(d, meta)
    meta["eis_kuzbass_filter_items_20261102"]["sources"][0]["sha256"] = "0" * 64
    assert not verified_kuzbass_filter_items(d, meta)
    assert "страна происхождения" not in source_bound_filter_signed_note(d, meta)
