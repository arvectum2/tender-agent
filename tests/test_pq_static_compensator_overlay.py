"""Regression guard for source-tier and price-status claims in PQ original research."""
import json
import re
from pathlib import Path


def test_2024_2025_static_compensator_source_overlay_is_conservative():
    root = Path(__file__).resolve().parents[1]
    path = root / "docs/market_intelligence/PQ_STATIC_COMPENSATOR_ORIGINALS_20261028.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "pq-static-compensator-evidence/1"
    cases = {item["registry_number"]: item for item in payload["cases"]}
    assert set(cases) == {"32414141662", "32515257631", "32413297739"}
    assert cases["32414141662"]["classification"] == "irrelevant"
    assert cases["32414141662"]["equipment_voltage_kv"] == "110"
    assert cases["32515257631"]["classification"] == "uncertain"
    assert cases["32515257631"]["equipment_voltage_kv"] is None
    assert cases["32413297739"]["classification"] == "pending_source_review"
    for case in cases.values():
        assert case["source_tier"] == "verified_public_eis_notice_page_not_soap_xml"
        assert re.fullmatch(r"[0-9a-f]{64}", case["notice_page_sha256"])
        assert case["files_saved"] == len(case["original_sha256"])
        assert all(re.fullmatch(r"[0-9a-f]{64}", sha) for sha in case["original_sha256"])
        assert case["signed_contract_verified"] is False
        assert case["contractual_supplier_verified"] is False
        assert case["executed_price_verified"] is False
    assert payload["new_signed_contracts"] == 0
    assert payload["new_verified_suppliers"] == 0
    assert payload["new_executed_prices"] == 0
