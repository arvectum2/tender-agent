"""Null-only EIS buyer INN guardrails; no live database writes."""
import pytest

from scripts.market_intelligence.enrich_pq_eis_buyer_inns_20261102 import (
    CASES,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def sample():
    n, inn, scope, _, _ = CASES[0]
    cid = f"223fz:{n}:lot1"
    data = {"canonical_id": cid, "procedure_id": n, "scope": scope,
            "customer": {"inn": inn}, "buyer_inn": None}
    row = {"id": cid, "owner": "tender-agent", "data": data,
           "hash": digest(data), "meta": {}}
    return CASES[0], row


def test_four_unique_eis_cases():
    assert len(CASES) == len({case[0] for case in CASES}) == 4
    assert all(len(case[1]) == 10 for case in CASES)


def test_old_null_is_accepted():
    case, row = sample()
    validate(case, row)


@pytest.mark.parametrize("mutator", [
    lambda r: r["data"].update(buyer_inn="7802312751"),
    lambda r: r["data"]["customer"].update(inn="0000000000"),
    lambda r: r.update(owner="other"),
    lambda r: r["meta"].update(eis_buyer_inn_20261102={"field": "buyer_inn"}),
])
def test_conflicting_fields_fail_closed(mutator):
    case, row = sample()
    mutator(row)
    with pytest.raises(RuntimeError, match="conflict"):
        validate(case, row)
