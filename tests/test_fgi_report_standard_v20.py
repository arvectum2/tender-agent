import json
from pathlib import Path

import pymupdf

from scripts.market_intelligence.render_fgi_full_deck import render

BASE = Path("data/market_intelligence/power_quality")
DOCS = Path("docs/market_intelligence")


def test_v20_one_new_source_bound_power_field():
    prior = json.loads((DOCS / "ARVECTUM_FGI_PQ_FIELD_AUDIT_20261031_V19.json").read_text())
    audit = json.loads((DOCS / "ARVECTUM_FGI_PQ_FIELD_AUDIT_20261031_V20.json").read_text())
    snap = json.loads((BASE / "fgi_client_deck_snapshot_20261031_v20.json").read_text())
    assert snap["unique_lots"] == 118
    assert snap["distinct_procedures"] == 107
    assert snap["eis_223_notices"] == 41
    assert audit["field_coverage"]["power"] == prior["field_coverage"]["power"] + 1
    assert sum(audit["field_coverage"].values()) == sum(prior["field_coverage"].values()) + 1
    case = next(x for x in snap["items"] if x["id"] == "commercial:351-062:lot1")
    assert "3000 кВАр" in case["power"]
    assert case["quantity"] == "2"
    assert case["voltage_kv"] == ""
    assert case["contract_price"] == ""
    for lang in ("ru", "en"):
        html, pages = render(snap, lang)
        assert pages == 258
        assert "3000 кВАр" in html
        pdf = pymupdf.open(DOCS / f"ARVECTUM_FGI_PQ_FULL_{lang.upper()}_20261031_V20.pdf")
        assert len(pdf) == pages
        case_pages = [p for p in pdf if "351-062" in p.get_text()]
        assert any("3000" in p.get_text() for p in case_pages)
        assert all(
            0 <= b[0] <= b[2] <= p.rect.width + 2
            and 0 <= b[1] <= b[3] <= p.rect.height + 2
            for p in case_pages for b in [block[:4] for block in p.get_text("blocks")]
        )
