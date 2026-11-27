"""Source-bound 31 Oct V4 must add only the three RAR/DOCX technical fields."""
import json
from pathlib import Path

from scripts.market_intelligence.render_fgi_full_deck import render

ROOT = Path("data/market_intelligence/power_quality")
DOC = Path("docs/market_intelligence")


def test_v4_exact_three_field_gain():
    old = json.loads((ROOT / "fgi_client_deck_snapshot_20261030_v3.json").read_text())
    new = json.loads((ROOT / "fgi_client_deck_snapshot_20261031_v4.json").read_text())
    assert old["unique_lots"] == new["unique_lots"] == 117
    assert old["distinct_procedures"] == new["distinct_procedures"] == 106
    assert old["eis_223_notices"] == new["eis_223_notices"] == 40
    changed = [(a["id"], k, a.get(k), b.get(k))
               for a, b in zip(old["items"], new["items"])
               for k in set(a) | set(b) if a.get(k) != b.get(k)]
    assert sorted(changed) == sorted([
        ("223fz:32616266007:lot1", "quantity", "", "5"),
        ("223fz:32616266007:lot1", "voltage_kv", "", "8.3"),
        ("223fz:32616266007:lot1", "power", "", "592 кВАр"),
    ])
    assert new["snapshot_date"] == "2026-10-31"


def test_v4_field_coverage_and_pdf():
    audit = json.loads((DOC / "ARVECTUM_FGI_PQ_FIELD_AUDIT_20261031_v4.json").read_text())
    assert audit["field_coverage"]["quantity"] == 46
    assert audit["field_coverage"]["voltage_kv"] == 18
    assert audit["field_coverage"]["power"] == 3
    for lang in ("RU", "EN"):
        p = DOC / f"ARVECTUM_FGI_PQ_FULL_{lang}_20261031_V4.pdf"
        assert p.stat().st_size > 1_000_000
        assert p.read_bytes()[:8].startswith(b"%PDF-1.")


def test_v4_date_and_source_bound_fields_in_render():
    new = json.loads((ROOT / "fgi_client_deck_snapshot_20261031_v4.json").read_text())
    html, pages = render(new, "ru")
    assert pages == 256
    assert "POWER QUALITY</b> / 31.10.2026" in html
    assert "592 кВАр" in html
