"""Exact SHA-bound export of the Angarsk anonymous commission offer."""
from copy import deepcopy

from scripts.market_intelligence import enrich_pq_angarsk_commission_20261102 as m
from scripts.market_intelligence.export_fgi_deck_snapshot import (
    source_bound_bid,
    source_bound_commission_note,
    verified_angarsk_commission,
)


def case():
    data = {
        "canonical_id": m.CID, "scope": "maintenance",
        "contract_registered_price_rub": "2639026.64",
        "winner": None, "contract_signatory": None,
        "evidence": [{"url": m.URL, "sha256": m.SHA}], **m.FIELDS,
    }
    metadata = {m.KEY: {
        "fields": m.FIELDS, "proof": {"url": m.URL, "sha256": m.SHA},
        "signed_supplier_verified": False, "paid_equipment_sale_verified": False,
    }}
    return data, metadata


def test_verified_bid_and_note():
    data, meta = case()
    assert verified_angarsk_commission(data, meta)
    assert source_bound_bid(data, meta) == "2590000.00"
    assert "не цена оборудования PQ" in source_bound_commission_note(data, meta)


def test_conflict_and_source_drift_fail_closed():
    data, meta = case()
    bad = deepcopy(meta)
    bad[m.KEY]["proof"]["sha256"] = "0" * 64
    assert not verified_angarsk_commission(data, bad)
    assert source_bound_bid(data, bad) is None
    data["bid"] = "2639026.64"
    assert not verified_angarsk_commission(data, meta)
