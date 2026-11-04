"""Acceptance gate for branded complete-corpus bilingual Arvectum client reports."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.market_intelligence.audit_fgi_report_fields import audit
from scripts.market_intelligence.render_fgi_full_deck import official_logo, render

ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/"data/market_intelligence/power_quality/fgi_client_deck_snapshot_20261030_v2.json"
AUDIT=ROOT/"docs/market_intelligence/ARVECTUM_FGI_PQ_FIELD_AUDIT_20261030_v2.json"

def source():
    return json.loads(SNAP.read_text(encoding="utf8"))

def test_genuine_logo_brandbook_provenance():
    official=(ROOT/"src/modules/tender_operator_agent_demo/assets/arvectum-logo-block.svg").read_text(encoding="utf8")
    logo=official_logo()
    assert "BRAND__Ok----Block" in logo
    assert logo.replace(' class="official-logo" role="img" aria-label="Arvectum"',"").replace("#00C8A0","#41b599")==official
    assert "#00C8A0" in logo
    assert "ᐱ" not in logo

def test_full_field_ledger_covers_every_case():
    data=source()
    result=audit(data)
    saved=json.loads(AUDIT.read_text(encoding="utf8"))
    assert data["unique_lots"]==117
    assert data["distinct_procedures"]==106
    assert data["eis_223_notices"]==40
    assert len(saved["cases"])==len(result["cases"])==117
    assert [x["id"] for x in saved["cases"]]==[x["id"] for x in data["items"]]
    assert sum(saved["source_grades"].values())==117
    assert saved["field_coverage"]==result["field_coverage"]
    assert all("missing_fields" in q and "next_priority" in q for q in saved["cases"])
    assert saved["field_coverage"]["voltage_kv"] <= 117

def test_bilingual_html_uniform_and_no_fictional_brand_mark():
    data=source()
    for lang in ("ru","en"):
        html,pages=render(data,lang)
        assert pages==2*117+22==256
        assert html.count('class="official-logo"')==pages
        assert html.count('data-case-id=')==117
        assert html.count('data-evidence-id=')==117
        assert "ᐱ Arvectum" not in html
        assert '#001432' in html and '#00C8A0' in html
        assert "JetBrains Mono" in html and "PT Sans" in html
        assert '/Users/master' not in html
        assert '/Volumes/ArvectumSSD' not in html

def test_pdfs_have_each_lot_twice_in_exact_order_and_embedded_fonts():
    pymupdf=pytest.importorskip("pymupdf")
    data=source()
    for lang in ("RU","EN"):
        path=ROOT/f"docs/market_intelligence/ARVECTUM_FGI_PQ_FULL_{lang}_20261030_V2.pdf"
        pdf=pymupdf.open(path)
        assert len(pdf)==256
        fonts=set()
        for ix,item in enumerate(data["items"]):
            first=pdf[21+ix*2]
            second=pdf[22+ix*2]
            for p in (first,second):
                assert p.rect.width==960 and p.rect.height==540
                assert item["id"] in p.get_text(sort=True)
                for b in p.get_text("blocks"):
                    assert -1 <= b[0] <= b[2] <= 961
                    assert -1 <= b[1] <= b[3] <= 541
                fonts.update(f[3] for f in p.get_fonts())
        assert any("PTSans" in f for f in fonts)
        assert any("JetBrainsMono" in f for f in fonts)
