"""EIS SHA-bound null-only enrichment safety regression."""
import copy

import pytest

from scripts.market_intelligence.enrich_pq_eis_contracts_20261031 import (
    CASES,
    prepare,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def row(case):
    d = {"canonical_id": case["cid"], "procedure_id": case["cid"].split(":")[1],
         "scope": case["scope"], "nmck_rub": case["nmck"],
         "customer": {"inn": case["inn"]}, "evidence": []}
    if "32616181358" in case["cid"]:
        d.update(contract_registry_number=case["num"],
                 contract_registered_price_rub="3050000.00",
                 registered_signed_contract_verified=True)
    return {"id": case["cid"], "owner": "tender-agent",
            "hash": digest(d), "rev": 2, "data": d, "meta": {}}


@pytest.mark.parametrize("case", CASES)
def test_source_bound_null_only(case):
    r = row(case)
    validate(case, r)
    d, meta, h = prepare(case, r, [{"url": "https://zakupki.gov.ru",
                                   "sha256": "a" * 64, "excerpt": "verified"}])
    assert h == digest(d)
    assert all(d[k] == v for k, v in case["fields"].items())
    assert meta["eis_20261031_contract_enrichment"]["paid_verified"] is False


@pytest.mark.parametrize("case", CASES)
def test_conflicts_fail_closed(case):
    for mode in ("old_field", "hash", "owner", "inn", "metadata"):
        r = copy.deepcopy(row(case))
        if mode == "old_field":
            r["data"][next(iter(case["fields"]))] = "already set"
            r["hash"] = digest(r["data"])
        elif mode == "hash":
            r["hash"] = "0" * 64
        elif mode == "owner":
            r["owner"] = "other"
        elif mode == "inn":
            r["data"]["customer"]["inn"] = "0000000000"
            r["hash"] = digest(r["data"])
        else:
            r["meta"]["eis_20261031_contract_enrichment"] = {}
        with pytest.raises(RuntimeError, match="CAS"):
            validate(case, r)
