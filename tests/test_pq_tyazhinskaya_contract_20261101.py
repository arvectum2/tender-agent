"""Null-only signed registry enrichment must not infer 110kV design as equipment sales."""
import pytest

from scripts.market_intelligence.enrich_pq_missing_field import digest
from scripts.market_intelligence.enrich_pq_tyazhinskaya_contract_20261101 import (
    CID,
    FIELDS,
    validate,
)


def make_row():
    d = {"canonical_id":CID, "procedure_id":"32615937898", "scope":"design_and_survey_only",
             "market_scope":"adjacent_110kv_reactive_compensation_design_not_equipment_sale",
             "nmck_rub":"3050000.00", "commission_bid_rub":"3050000.00",
             "supplier_verified":False, "paid_verified":False,
             "pq_equipment_only_contract_rub":None}
    return {"id":CID,"owner":"tender-agent","data":d,"hash":digest(d),"rev":1,"meta":{}}

def test_contract_only_null_fields_and_no_supplier():
    r=make_row()
    validate(r, {"sources":[{"sha256":"a"*64},{"sha256":"b"*64}]})
    assert FIELDS["registered_signed_contract_verified"] is True
    assert "signed_supplier" not in FIELDS and "paid_amount" not in FIELDS

@pytest.mark.parametrize("field,value", [
    ("contract_number","old"), ("contract_registry_number","old"),
    ("contract_registered_price_rub","1"), ("registered_signed_contract_verified",False),
    ("supplier_verified",True), ("scope","core_equipment"),
])
def test_conflicts_fail_closed(field,value):
    r=make_row();r["data"][field]=value;r["hash"]=digest(r["data"])
    with pytest.raises(RuntimeError):
        validate(r, {"sources":[{"sha256":"a"*64},{"sha256":"b"*64}]})


def test_client_snapshot_verifier_source_bound():
    from scripts.market_intelligence.enrich_pq_tyazhinskaya_contract_20261101 import (
        FILES,
    )
    from scripts.market_intelligence.export_fgi_deck_snapshot import (
        verified_tyazhinskaya_20261101,
    )

    r = make_row()
    r["data"].update(FIELDS)
    r["data"]["evidence"] = [
        {"url": url, "sha256": sha} for _, sha, url in FILES
    ]
    meta = {
        "eis_tyazhinskaya_20261101_registered_contract": {
            "sources": [{"url": url, "sha256": sha} for _, sha, url in FILES],
            "supplier_verified": False, "payment_verified": False,
        }
    }
    assert verified_tyazhinskaya_20261101(r["data"], meta)
    r["data"]["paid_verified"] = True
    assert not verified_tyazhinskaya_20261101(r["data"], meta)
