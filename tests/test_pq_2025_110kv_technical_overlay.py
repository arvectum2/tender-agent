"""Source-bound 110 kV exclusion and no signed price promotion."""
import json
from pathlib import Path


def test_2025_technical_exclusion_and_no_market_sales():
    path = (Path(__file__).resolve().parents[1]
            / "docs/market_intelligence/PQ_2025_110KV_ORIGINALS_20261028.json")
    item = json.loads(path.read_text(encoding="utf-8"))
    assert item["notice_id"] == "32515257631"
    assert item["equipment_rated_voltage_kv"] == 110
    assert item["classification"] == "irrelevant"
    assert item["signed_contract_verified"] is False
    assert item["winner_verified"] is False
    assert item["executed_price_verified"] is False
    assert item["market_total_rub"] is None
    assert len(item["original_technical_docx_sha256"]) == 2
