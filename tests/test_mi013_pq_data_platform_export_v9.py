"""v9 Data Platform JSONL keeps stable keys and does not invent contract results."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/market_intelligence/export_pq_data_platform_v9.py"


def lines():
    p = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=30, check=True)
    return [json.loads(line) for line in p.stdout.splitlines() if line.strip()]


def test_v9_exports_64_distinct_stable_resources():
    rows = lines()
    assert len(rows) == 64
    assert len({row["resource_id"] for row in rows}) == 64
    assert len({row["external_id"] for row in rows}) == 64
    assert all(row["metadata"]["data_version"] == "v9" for row in rows)
    for row in rows:
        expected = hashlib.sha256(row["external_id"].encode("utf-8")).hexdigest()
        assert row["resource_id"] == expected[:48]
        assert row["canonical_uri"] == f"urn:arvectum:pq:procurement:{expected}"
        assert row["metadata"]["research_not_market_population"] is True


def test_v9_rosseti_components_prices_are_not_contract_values():
    rows = lines()
    new = [row for row in rows if row["external_id"] in {
        "223fz:32515029641:lot1",
        "223fz:32514947144:lot1",
        "223fz:32515225588:lot1",
        "223fz:32515208744:lot1",
    }]
    assert len(new) == 4
    for row in new:
        assert row["metadata"]["winning_supplier_only_if_verified"] is None
        assert row["metadata"]["original_primary_registry_verified"] is False
        assert row["metadata"]["reported_price_kind"] == "initial_price_not_contract"
        assert row["metadata"]["source_urls"]
        assert row["source_record"]["equipment_voltage_kv"] is None
