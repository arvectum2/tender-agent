"""Every research lot must appear exactly once in each bilingual slide dossier."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.market_intelligence.render_fgi_full_deck import render

ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/'data/market_intelligence/power_quality/fgi_client_deck_snapshot_20261030.json'

def test_source_snapshot_has_complete_unique_corpus():
    obj=json.loads(SNAP.read_text(encoding='utf8'))
    ids=[q['id'] for q in obj['items']]
    assert obj['unique_lots']==len(ids)>=115
    assert len(ids)==len(set(ids))
    assert obj['distinct_procedures']==len({q.split(':')[1] for q in ids})

def test_both_html_decks_have_one_dossier_per_lot():
    obj=json.loads(SNAP.read_text(encoding='utf8'))
    for lang in ('ru','en'):
        out,pages=render(obj,lang)
        assert pages==2*len(obj['items'])+22
        assert out.count('data-evidence-id=')==len(obj['items'])
        assert out.count('data-case-id=')==len(obj['items'])
        assert '<a href=' in out
        assert '/Volumes/ArvectumSSD' not in out
        assert '/Users/master' not in out
        assert 'ARVECTUM_MACBOOK_API_TOKEN' not in out

def test_final_pdfs_page_count_and_per_page_id():
    pymupdf=pytest.importorskip("pymupdf")
    obj=json.loads(SNAP.read_text(encoding='utf8'))
    for lang in ('RU','EN'):
        p=ROOT/f'docs/market_intelligence/ARVECTUM_FGI_PQ_FULL_{lang}_20261030.pdf'
        d=pymupdf.open(p)
        assert len(d)==len(obj['items'])+21
        for index,lot in enumerate(obj['items']):
            pg=d[20+index]
            assert lot['id'] in pg.get_text(sort=True)
            assert pg.rect.width==960 and pg.rect.height==540
