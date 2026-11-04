"""Acceptance: source-bound reference case, one slide and complete supporting dossier."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.market_intelligence.render_fgi_full_deck import official_logo
from scripts.market_intelligence.render_reto_reference_slide import render

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"data/market_intelligence/power_quality/exemplars/reto_32616181358_20261031.v1.json"

def data():
    return json.loads(SOURCE.read_text(encoding="utf8"))

def test_original_document_evidence_and_field_completeness():
    x=data(); hw=x["hardware"]; fields=x["field_evidence"]
    assert x["case_id"]=="223fz:32616181358:lot1"
    assert x["buyer_inn"]=="7724646338"
    assert hw["voltage_kv"]==12
    assert sum(a["qty"] for a in hw["items"])==10
    assert sum(a["qty"]*a["power_each_kvar"] for a in hw["items"])==5250
    assert sum(a["qty"]*a["nmc_unit_inc_vat_rub"] for a in hw["items"])==3078500
    assert sum(a["qty"]*a["archived_contract_unit_rub"] for a in hw["items"])==3050000
    assert x["discount_rub"]==x["nmck_rub"]-x["winning_bid_rub"]==28500
    assert x["winner_inn"]=="7720494275"
    assert float(x["participation"][2]["bid_inc_vat22_rub"])==1960906
    assert x["signed_supplier_verified"] is False
    assert x["physical_delivery_verified"] is False
    assert x["payment_verified"] is False
    assert len(fields)>=50
    assert len({f["field"] for f in fields})==len(fields)
    assert sum(f["status"]=="not_verified" for f in fields)>=8
    sources=x["source_provenance"]
    assert sources["PROTOCOL"]["sha"]=="92874d098feb7dc6c283bd7b66c5218e11e472f27eddffc75edd6613fb5b21ef"
    assert sources["TZ"]["sha"]=="9ceb44be68abcf07729cb9045b1a3ce7b54456810c93c9a32885781d3a578032"
    assert sources["EIS"]["grade"].startswith("archived")
    assert all(s["url"].startswith("https://") for s in sources.values())
    assert all(set(f["source_ids"]).issubset(sources) for f in fields)

def test_bilingual_deck_one_real_logo_and_three_pages():
    x=data()
    assert "BRAND__Ok----Block" in official_logo()
    for lang in ("ru","en"):
        text=render(x,lang)
        assert text.count('class="slide"')==3
        assert text.count('class="official-logo"')==3
        assert "ᐱ" not in text
        assert '3 078 500 ₽' in text if lang=="ru" else 'RUB 3,078,500' in text
        assert "12" in text
        assert "/Users/master" not in text and "/Volumes/ArvectumSSD" not in text
        for code in ("TZ","PROTOCOL","ETP","EIS"):
            assert x["source_provenance"][code]["url"] in text.replace("&amp;","&")

def test_pdf_pagination_and_links():
    pdfmod=pytest.importorskip("pymupdf")
    for lang in ("RU","EN"):
        path=ROOT/f"docs/market_intelligence/ARVECTUM_RETO_REFERENCE_{lang}_20261031.pdf"
        pdf=pdfmod.open(path)
        assert len(pdf)==3
        assert sum(len(pg.get_links()) for pg in pdf)>=4
        assert all(pg.rect.width==960 and pg.rect.height==540 for pg in pdf)
        fonts=set()
        for page in pdf:
            for b in page.get_text("blocks"):
                assert -1 <= b[0] <= b[2] <= 961
                assert -1 <= b[1] <= b[3] <= 541
            fonts.update(f[3] for f in page.get_fonts())
        assert any("PTSans" in name for name in fonts)
        assert any("JetBrainsMono" in name for name in fonts)
        assert "7720494275" in pdf[0].get_text()
        one=pdfmod.open(ROOT/f"docs/market_intelligence/ARVECTUM_RETO_REFERENCE_SLIDE_{lang}_20261031.pdf")
        assert len(one)==1
        assert one[0].get_text()==pdf[0].get_text()
