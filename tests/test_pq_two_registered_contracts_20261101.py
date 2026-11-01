"""Source-bound EIS contract enrichment does not misstate equipment sales."""
from scripts.market_intelligence.enrich_pq_eis_contracts_20261031 import (
    prepare,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest
from scripts.market_intelligence.enrich_pq_two_registered_contracts_20261101 import (
    CASES,
)


def row(case):
    data = {
        "canonical_id": case["cid"], "procedure_id": case["cid"].split(":")[1],
        "scope": case["scope"], "nmck_rub": case["nmck"],
        "customer": {"name": "buyer", "inn": case["inn"]},
        "evidence": [], "supplier_verified": False,
        "paid_amount_rub": None, "pq_equipment_only_contract_rub": None,
    }
    return {"id": case["cid"], "owner": "tender-agent", "data": data,
            "hash": digest(data), "rev": 2, "meta": {}}


def test_two_distinct_eis_contracts_no_paid_sale():
    assert len({c["cid"] for c in CASES}) == 2
    assert {c["scope"] for c in CASES} == {"supply", "design"}
    assert sum(len(c["fields"]) for c in CASES) == 11
    for c in CASES:
        assert c["fields"]["registered_signed_contract_verified"] is True
        assert "paid_amount_rub" not in c["fields"]
        assert "supplier_verified" not in c["fields"]
        assert "pq_equipment_only_contract_rub" not in c["fields"]


def test_old_null_and_identity_cas():
    for c in CASES:
        r = row(c)
        validate(c, r)
        r["data"]["contract_number"] = "existing"
        r["hash"] = digest(r["data"])
        try:
            validate(c, r)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Must reject non-null conflicting field")


def test_prepared_preserves_unknown_supplier():
    for c in CASES:
        r = row(c)
        src = [{"url": "https://zakupki.gov.ru", "sha256": "a" * 64, "excerpt": "verified"}]
        new, meta, h = prepare(c, r, src)
        assert new["supplier_verified"] is False
        assert new["paid_amount_rub"] is None
        assert new["pq_equipment_only_contract_rub"] is None
        assert new["contract_registered_price_rub"] == c["fields"]["contract_registered_price_rub"]
        assert meta["eis_20261031_contract_enrichment"]["paid_verified"] is False
        assert digest(new) == h
