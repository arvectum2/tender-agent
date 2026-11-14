"""Regression: EIS 11.55 kV BSK registered contract is not an executed sale."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data/market_intelligence/power_quality/fgi_client_deck_snapshot_20261101_v38.json"


def test_bsk_1155kv_contract_is_source_bound_and_not_paid_sale():
    report = json.loads(SNAP.read_text(encoding="utf-8"))
    assert report["unique_lots"] == 120
    assert report["distinct_procedures"] == 109
    assert report["eis_223_notices"] == 43
    case, = [r for r in report["items"] if r["id"] == "223fz:32615637628:lot1"]
    assert case["technical"]["voltage_kv"] == "11.55"
    assert case["technical"]["power_kvar_per_unit"] == "500"
    assert case["technical"]["quantity"] == "2"
    assert case["contract_price"] == "484998.80"
    assert case["contract_registry_number"] == "52460069527260002170000"
    assert case["nmck"] == "531888.28"
    assert case["signed_supplier_verified"] is False
    assert case["paid_verified"] is False
    assert not case["paid_amount"]
    assert len(case["source_urls"]) == 3
    assert all(len(s["sha"]) == 64 for s in case["source_urls"])


def test_v38_is_versioned_without_replacing_v37():
    for lang in ("RU", "EN"):
        for version in ("V37", "V38"):
            p = ROOT / f"docs/market_intelligence/ARVECTUM_FGI_PQ_FULL_{lang}_20261101_{version}.pdf"
            assert p.is_file() and p.stat().st_size > 1_000_000
    client = (ROOT / "docs/market_intelligence/POWER_QUALITY_CLIENT_PREVIEW_20261024.html").read_text(encoding="utf-8")
    assert "120" in client
