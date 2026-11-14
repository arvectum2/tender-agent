"""EIS-source-bound 10 kV design contract, not a signed equipment sale."""
import json
from pathlib import Path

import pymupdf

from scripts.market_intelligence.export_fgi_deck_snapshot import source_bound_bid

DOCS = Path("docs/market_intelligence")
SNAP = Path("data/market_intelligence/power_quality/fgi_client_deck_snapshot_20261031_v23.json")
CID = "223fz:32616280467:lot1"
PROTOCOL_SHA = "32b17b6891e29ba60734590f6ff2bbf029c082c8bc75262889da713b92f38554"


def test_v23_source_bound_commission_bid_requires_original_sha():
    data = {"canonical_id": CID, "commission_first_place_application": "1",
            "commission_first_place_bid_rub": "3680106.21"}
    proof = {"eis_20261031_contract_enrichment": {
        "fields": {"commission_first_place_bid_rub": "3680106.21"},
        "sources": [{"sha256": PROTOCOL_SHA}]}}
    assert source_bound_bid(data, proof) == "3680106.21"
    assert source_bound_bid(data, {}) is None
    assert source_bound_bid(data, {"eis_20261031_contract_enrichment": {
        **proof["eis_20261031_contract_enrichment"],
        "sources": [{"sha256": "0" * 64}]}}) is None


def test_v23_signed_design_dossier_has_no_hardware_supplier_or_payment():
    data = json.loads(SNAP.read_text(encoding="utf8"))
    assert (data["unique_lots"], data["distinct_procedures"], data["eis_223_notices"]) == (118, 107, 41)
    case = next(x for x in data["items"] if x["id"] == CID)
    assert case["scope"] == "design"
    assert case["voltage_kv"] == "10"
    assert case["bid"] == "3680106.21"
    assert case["contract_price"] == "3680106.21"
    assert case["contract_no"] == "2640-004569"
    assert case["contract_date"] == "2026-09-03"
    assert case["signed_contract_verified"] is True
    assert case["signed_supplier_verified"] is False
    assert case["paid_verified"] is False
    assert not case["winner"] and not case["equipment_only_price"] and not case["paid_amount"]
    for lang in ("RU", "EN"):
        with pymupdf.open(DOCS / f"ARVECTUM_FGI_PQ_FULL_{lang}_20261031_V23.pdf") as pdf:
            assert len(pdf) == 258
            pages = [p.get_text() for p in pdf if "2640-004569" in p.get_text()]
            assert pages and any("3 680 106" in t or "3,680,106" in t for t in pages)
