import copy

import pytest

from scripts.market_intelligence.enrich_pq_bidzaar_351062 import (
    CARD_URL,
    CID,
    DOC_SHA,
    VALUE,
    updated,
    validate,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def row():
    data = {"quantity": 2, "power": None, "evidence": [{"url": CARD_URL}]}
    return {
        "id": CID, "owner": "tender-agent", "rev": 2,
        "hash": digest(data), "data": data, "meta": {},
    }


def test_null_only_source_bound_update():
    r = row()
    validate(r)
    data, meta = updated(r)
    assert data["power"] == VALUE
    assert data["quantity"] == 2
    assert data["evidence"][-1]["sha256"] == DOC_SHA
    assert meta["bidzaar_351062_p2"]["previous_hash"] == r["hash"]
    assert r["data"]["power"] is None


@pytest.mark.parametrize("change", ["non_null", "owner", "source", "quantity", "hash"])
def test_conflict_fail_closed(change):
    r = copy.deepcopy(row())
    if change == "non_null":
        r["data"]["power"] = "conflicting"
    elif change == "owner":
        r["owner"] = "another-owner"
    elif change == "source":
        r["data"]["evidence"] = []
    elif change == "quantity":
        r["data"]["quantity"] = 3
    else:
        r["hash"] = "0" * 64
    if change != "hash":
        r["hash"] = digest(r["data"])
    with pytest.raises(RuntimeError):
        validate(r)
