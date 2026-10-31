"""No DB/network writes: null-only CAS preconditions for the EIS UKRM contract."""
import pytest

from scripts.market_intelligence.enrich_pq_eis_contract_32515582393 import (
    CID,
    FIELDS,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def _row():
    data = {
        "canonical_id": CID,
        "procedure_id": "32515582393",
        "scope": "supply",
        "nmck_rub": "5880000",
        "customer": {"inn": "0277071467"},
    }
    return {
        "id": CID,
        "owner": "tender-agent",
        "hash": digest(data),
        "data": data,
        "meta": {},
    }


def test_eis_contract_only_enriches_missing_fields():
    row = _row()
    evidence = {"sources": [{"sha256": "a" * 64}, {"sha256": "b" * 64}]}
    validate(row, evidence)
    assert len(FIELDS) == 5
    assert FIELDS["contract_registered_price_rub"] == "4850000.00"


@pytest.mark.parametrize("field,value", [
    ("contract_registry_number", "already present"),
    ("contract_registered_price_rub", "4900000.00"),
    ("registered_signed_contract_verified", False),
])
def test_eis_contract_refuses_conflicting_existing_value(field, value):
    row = _row()
    row["data"][field] = value
    row["hash"] = digest(row["data"])
    with pytest.raises(RuntimeError, match="CAS"):
        validate(row, {"sources": [{}, {}]})


def test_eis_contract_refuses_wrong_identity_or_source_count():
    row = _row()
    row["data"]["customer"]["inn"] = "0000000000"
    row["hash"] = digest(row["data"])
    with pytest.raises(RuntimeError, match="CAS"):
        validate(row, {"sources": [{}, {}]})
    row = _row()
    with pytest.raises(RuntimeError, match="CAS"):
        validate(row, {"sources": [{}]})
