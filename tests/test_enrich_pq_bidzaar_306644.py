"""306-644 source-bound, null-only enrichment regression tests."""
import pytest

from scripts.market_intelligence.enrich_pq_bidzaar_306644 import (
    FIELDS,
    prepared,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def row():
    data = {
        "canonical_id": "commercial:306-644:lot35", "scope": "epc", "family": "ukrm",
        "customer": {"name": "СИБСТЕКЛО"}, "quantity": 1,
        "quantity_unit": "усл.ед",
        "evidence": [{"url": "https://bidzaar.com/app/process/light/019ce668-617b-7b1a-861e-113ed78182af"}],
    }
    return {"id": data["canonical_id"], "owner": "tender-agent",
            "data": data, "hash": digest(data), "rev": 3, "meta": {}}


def test_enrichment_preserves_service_unit_and_no_sale():
    r = row()
    validate(r)
    data, meta, content_hash = prepared(r, {"url": "source", "sha256": "abc"})
    assert all(data[k] == v for k, v in FIELDS.items())
    assert data["quantity"] == 1 and data["quantity_unit"] == "усл.ед"
    assert meta["bidzaar_306644_p2"]["physical_ukrm_units"] == 2
    assert meta["bidzaar_306644_p2"]["not_an_equipment_sale"] is True
    assert digest(data) == content_hash


@pytest.mark.parametrize("key,value", [
    ("power", "900"), ("quantity", 2), ("scope", "supply"),
])
def test_conflicts_fail_closed(key, value):
    r = row()
    r["data"][key] = value
    with pytest.raises(RuntimeError):
        validate(r)


def test_owner_mismatch_fails_closed():
    r = row()
    r["owner"] = "other"
    with pytest.raises(RuntimeError):
        validate(r)



def test_client_note_requires_exact_sha_and_customer_supplied_equipment():
    from scripts.market_intelligence.export_fgi_deck_snapshot import (
        source_bound_bidzaar_306644_note,
    )

    r = row()
    r["data"].update(FIELDS)
    r["data"]["evidence"].append({
        "url": "https://bidzaar.com/api/filestorage/files/download/8042258e-bd58-4efc-9f98-b00db6113f82",
        "sha256": "28c970162cc7b36cff91df3b64ea4168c5717cc43554aea162440e6d10272516",
    })
    meta = {"bidzaar_306644_p2": {
        "source_sha256": "28c970162cc7b36cff91df3b64ea4168c5717cc43554aea162440e6d10272516",
        "customer_provided_equipment": True, "not_an_equipment_sale": True,
    }}
    note = source_bound_bidzaar_306644_note(r["data"], meta)
    assert "Оборудование предоставляет заказчик" in note
    meta["bidzaar_306644_p2"]["not_an_equipment_sale"] = False
    assert source_bound_bidzaar_306644_note(r["data"], meta) is None
