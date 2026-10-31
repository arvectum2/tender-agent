"""V9 only adds a first-party verified buyer INN, not a signed supplier."""
import json
from pathlib import Path

from scripts.market_intelligence.export_fgi_deck_snapshot import source_bound_buyer_inn
from scripts.market_intelligence.render_fgi_full_deck import render

ROOT = Path("data/market_intelligence/power_quality")
DOC = Path("docs/market_intelligence")


def test_buyer_inn_fails_without_source():
    assert source_bound_buyer_inn({"buyer_inn": "2310031475", "evidence": []}, {}) is None


def test_v9_one_case_and_one_field():
    a = json.loads((ROOT / "fgi_client_deck_snapshot_20261031_v8.json").read_text())
    b = json.loads((ROOT / "fgi_client_deck_snapshot_20261031_v9.json").read_text())
    assert a["unique_lots"] == b["unique_lots"] == 117
    assert b["distinct_procedures"] == 106 and b["eis_223_notices"] == 40
    changed = [(x["id"], k) for x, y in zip(a["items"], b["items"])
               for k in set(x) | set(y) if x.get(k) != y.get(k)]
    assert changed == [("commercial:4617521:lot1", "buyer_inn")]
    row = next(x for x in b["items"] if x["id"] == "commercial:4617521:lot1")
    assert row["buyer_inn"] == "2310031475"
    assert row["signed_supplier_verified"] is False and row["contract_price"] == ""
    audit = json.loads((DOC / "ARVECTUM_FGI_PQ_FIELD_AUDIT_20261031_v9.json").read_text())
    prior = json.loads((DOC / "ARVECTUM_FGI_PQ_FIELD_AUDIT_20261031_v8.json").read_text())
    assert audit["field_coverage"]["buyer_inn"] == prior["field_coverage"]["buyer_inn"] + 1
    html, pages = render(b, "ru")
    assert pages == 256 and "2310031475" in html
