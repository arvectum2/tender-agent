"""Independent acceptance for source-frozen 406-slide bilingual procurement reports."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.market_intelligence.render_fgi_20261104 import render, summary_pages

ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/"data/market_intelligence/power_quality/fgi_full_corpus_20261104.v1.json"
AUDIT=ROOT/"docs/market_intelligence/ARVECTUM_FGI_PQ_AUDIT_20261104.json"

def corpus():
    return json.loads(SNAP.read_text(encoding="utf8"))

def test_snapshot_identity_provenance_and_financial_boundaries():
    d=corpus();rows=d["items"]
    assert len(rows)==d["unique_lots"]==123
    assert len({r["id"] for r in rows})==123
    assert d["distinct_procedures"]==112
    assert d["eis_223_notices"]==45
    assert d["eis_223_lots"]==46
    assert sum(d["scope_counts"].values())==123
    assert sum(d["grade_counts"].values())==123
    assert d["grade_counts"]=={"A":43,"B":26,"C":54}
    assert sum(len(r["sources"]) for r in rows)==294
    assert sum(bool(r["protocol_bidders"]) for r in rows)==6
    assert sum(bool(r["contract_signed_verified"]) for r in rows)==20
    assert sum(bool(r["signed_supplier_verified"]) for r in rows)==0
    assert sum(bool(r["paid_verified"]) for r in rows)==0
    assert all(r["review_status"]=="unreviewed" for r in rows)

def test_html_layout_and_genuine_brand_complete_cases():
    d=corpus()
    assert len(summary_pages(d,"ru"))==21
    for lang in ("ru","en"):
        source,npages,nsummary,nindex=render(d,lang)
        assert npages==406 and nsummary==21 and nindex==8
        assert source.count('class="official-logo"')==406
        assert source.count('id="case-')==123
        assert source.count('class="slide')==406
        assert "ᐱ Arvectum" not in source
        assert "JetBrains Mono" in source and "PT Sans" in source
        assert "#001432" in source and "#00C8A0" in source
        assert "/Users/master" not in source and "/Volumes/ArvectumSSD" not in source
        assert "32616181358" in source

def test_audit_and_machine_readable_report_reconcile():
    d=corpus();audit=json.loads(AUDIT.read_text(encoding="utf8"))
    assert audit["lots"]==len(audit["case_coverage"])==123
    assert [r["id"] for r in d["items"]]==[r["id"] for r in audit["case_coverage"]]
    assert audit["field_counts"]["protocol_bidders"]==6
    ledger=(ROOT/"docs/market_intelligence/ARVECTUM_FGI_PQ_SOURCE_LEDGER_20261104.md").read_text()
    report=(ROOT/"docs/market_intelligence/ARVECTUM_FGI_PQ_FULL_REPORT_20261104.md").read_text()
    assert ledger.count("[Открыть источник](")==294
    assert all(r["id"] in report and r["id"] in ledger for r in d["items"])
    expected_sha=hashlib.sha256((json.dumps(d,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()).hexdigest()
    assert expected_sha in report
    assert "406" in report

def test_pdfs_each_lot_on_three_pages_plus_six_original_protocol_appendices():
    fitz=pytest.importorskip("pymupdf")
    d=corpus();rows=d["items"];extras=[r for r in rows if r["protocol_bidders"]]
    for L in ("RU","EN"):
        path=ROOT/f"docs/market_intelligence/ARVECTUM_FGI_PQ_EXHAUSTIVE_{L}_20261104.pdf"
        pdf=fitz.open(path)
        assert len(pdf)==406
        assert all(page.rect.width==960 and page.rect.height==540 for page in pdf)
        fonts=set();linked=0
        for i,row in enumerate(rows):
            for j in range(3):
                page=pdf[30+i*3+j]
                assert row["id"] in page.get_text(sort=True),(L,i,j,row["id"])
                linked+=len(page.get_links())
                for block in page.get_text("blocks"):
                    assert -1 <= block[0] <= block[2] <= 961
                    assert -1 <= block[1] <= block[3] <= 541
                fonts.update(f[3] for f in page.get_fonts())
        for i,row in enumerate(extras):
            assert row["id"] in pdf[399+i].get_text(sort=True)
        assert linked>=200
        assert any("PTSans" in font for font in fonts)
        assert any("JetBrainsMono" in font for font in fonts)
        assert pdf[0].rect.width==960
