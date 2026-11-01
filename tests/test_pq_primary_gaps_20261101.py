"""Focused immutable original and field mapping tests."""
from scripts.market_intelligence.enrich_pq_primary_gaps_20261101 import (
    CASES,
    prepare,
    verify,
)


def test_first_party_receipts_and_quotes():
    for case in CASES:
        source = verify(case)
        assert source["sha256"] == case["sha"]
        assert source["url"] == case["url"]


def test_null_only_field_preparation():
    for case in CASES:
        row = {"data": {"customer": {"inn": None}, "evidence": []},
               "meta": {}, "hash": "old", "rev": 2}
        source = {"url": case["url"], "sha256": case["sha"]}
        data, meta, digest = prepare(case, row, source)
        assert len(digest) == 64
        assert data["source_urls"][0]["sha"] == case["sha"]
        assert meta["primary_gap_20261101"]["previous_revision"] == 2
        if case["field"] == "customer.inn":
            assert data["customer"]["inn"] == case["value"]
        else:
            assert data["voltage_kv"] == "35"
