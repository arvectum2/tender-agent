"""Regression: V3 changes one source-backed field, never the frozen V2."""
import json
from pathlib import Path

ROOT = Path("data/market_intelligence/power_quality")
DOC = Path("docs/market_intelligence")


def test_v3_exact_source_bound_delta():
    old = json.loads((ROOT / "fgi_client_deck_snapshot_20261030_v2.json").read_text())
    new = json.loads((ROOT / "fgi_client_deck_snapshot_20261030_v3.json").read_text())
    assert old["unique_lots"] == new["unique_lots"] == 117
    assert old["distinct_procedures"] == new["distinct_procedures"] == 106
    assert old["eis_223_notices"] == new["eis_223_notices"] == 40
    changed = [(a["id"], k, a.get(k), b.get(k))
               for a, b in zip(old["items"], new["items"])
               for k in set(a) | set(b) if a.get(k) != b.get(k)]
    assert changed == [("commercial:4657777:lot1", "quantity", "", "6")]


def test_v3_coverage_and_pdfs():
    audit = json.loads((DOC / "ARVECTUM_FGI_PQ_FIELD_AUDIT_20261030_v3.json").read_text())
    assert audit["field_coverage"]["quantity"] == 45
    for lang in ("RU", "EN"):
        p = DOC / f"ARVECTUM_FGI_PQ_FULL_{lang}_20261030_V3.pdf"
        assert p.stat().st_size > 1_000_000
        assert p.read_bytes()[:8].startswith(b"%PDF-1.")
