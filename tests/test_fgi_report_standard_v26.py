"""YUTEK 10kV source-bound signed registry, without supplier or paid-sale claims."""
import json
from pathlib import Path

import pymupdf

ROOT = Path("data/market_intelligence/power_quality")
DOCS = Path("docs/market_intelligence")
CID = "223fz:32413764701:lot1"


def test_v26_signed_registry_quantity_not_paid_sale():
    snap = json.loads((ROOT / "fgi_client_deck_snapshot_20261101_v26.json").read_text())
    assert (snap["unique_lots"], snap["distinct_procedures"], snap["eis_223_notices"]) == (118, 107, 41)
    case = next(x for x in snap["items"] if x["id"] == CID)
    assert case["quantity"] == "1"
    assert case["voltage_kv"] == "10"
    assert case["contract_no"] == "13790-сн/24"
    assert case["contract_date"] == "2024-08-09"
    assert case["contract_price"] == "4077120.00"
    assert case["signed_contract_verified"] is True
    assert case["signed_supplier_verified"] is False
    assert case["paid_verified"] is False
    assert not case["winner"] and not case["equipment_only_price"]


def test_v26_bilingual_pdfs_have_full_case_count():
    for lang in ("RU", "EN"):
        path = DOCS / f"ARVECTUM_FGI_PQ_FULL_{lang}_20261101_V26.pdf"
        with pymupdf.open(path) as pdf:
            assert len(pdf) == 258
            assert any("13790" in page.get_text() for page in pdf)
