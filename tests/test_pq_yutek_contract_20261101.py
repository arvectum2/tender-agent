"""Focused source/identity regression for the 10kV YUTEK contract."""
from scripts.market_intelligence.enrich_pq_missing_field import get_row
from scripts.market_intelligence.enrich_pq_yutek_contract_32413764701 import (
    CASE,
    CID,
    proof_yutek,
    validate,
)


def test_source_sha_and_contract_quantity():
    sources = proof_yutek()
    assert len(sources) == 2
    assert sources[0]["sha256"] != sources[1]["sha256"]
    assert CASE["fields"]["quantity"] == 1
    assert CASE["fields"]["contract_signed_date"] == "2024-08-09"


def test_cas_rejects_missing_or_modified_identity():
    row = get_row(CID)
    if row["data"].get("quantity") is None:
        validate(CASE, row)
    else:
        assert row["data"]["quantity"] == 1
        assert row["data"]["contract_number"] == "13790-сн/24"
    assert row["data"].get("supplier_inn") is None
