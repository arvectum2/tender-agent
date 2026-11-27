from scripts.market_intelligence.export_fgi_deck_snapshot import source_bound_bid


def test_source_bound_bid_requires_provenance():
    data = {"bid": "79101498.40"}
    assert source_bound_bid(data, {}) is None
    proof = {"roseltorg_field_enrichment": {
        "role": "bidder_not_winner", "fields": {"bid": "79101498.40"},
        "source_sha256": ["a" * 64, "b" * 64]}}
    assert source_bound_bid(data, proof) == "79101498.40"
    assert source_bound_bid({"bid": "1.00"}, proof) is None
    assert source_bound_bid({"commission_bid_rub": "2.00"}, {}) == "2.00"
