import copy

import pytest

from scripts.market_intelligence.enrich_pq_lopcha_p0_20261031 import (
    CASES,
    INN,
    transaction,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def row(n):
    d = {"canonical_id": f"223fz:{n}:lot1", "procedure_id": n,
         "scope": CASES[n][0], "buyer_inn": None, "source_urls": None}
    return {"id": d["canonical_id"], "owner": "tender-agent", "data": d,
            "hash": digest(d), "rev": 1, "meta": {}}


@pytest.mark.parametrize("number", list(CASES))
def test_fail_closed_null_and_identity(number):
    r = row(number)
    validate(number, r)
    for key, value in (("buyer_inn", INN), ("source_urls", []),
                       ("procedure_id", "other")):
        changed = copy.deepcopy(r)
        changed["data"][key] = value
        changed["hash"] = digest(changed["data"])
        with pytest.raises(RuntimeError):
            validate(number, changed)


def test_atomic_transaction_guards():
    rows = []
    for n in CASES:
        r = row(n)
        d = {**r["data"], "buyer_inn": INN,
             "source_urls": [{"sha": "a"*64}]}
        rows.append((n, r, d, {}, digest(d), {"sha256": "a"*64}))
    sql = transaction(rows, {"rows": 118})
    assert sql.count("UPDATE dp_records") == 3
    assert sql.count("UPDATE dp_resources") == 3
    assert "SERIALIZABLE" in sql
    assert "IS NULL" in sql
    assert sql.endswith("COMMIT;")
