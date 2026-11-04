"""V8 adds only source-bound RAD/EIS 12 kV supply facts to V7."""
import json
from pathlib import Path

from scripts.market_intelligence.render_fgi_full_deck import render

ROOT = Path('data/market_intelligence/power_quality')
DOC = Path('docs/market_intelligence')


def test_v8_only_one_case_and_six_visible_fields():
    a = json.loads((ROOT / 'fgi_client_deck_snapshot_20261031_v7.json').read_text())
    b = json.loads((ROOT / 'fgi_client_deck_snapshot_20261031_v8.json').read_text())
    assert (a['unique_lots'], b['unique_lots']) == (117, 117)
    assert b['distinct_procedures'] == 106 and b['eis_223_notices'] == 40
    changed = [(x['id'], k, x.get(k), y.get(k)) for x, y in zip(a['items'], b['items'])
               for k in set(x) | set(y) if x.get(k) != y.get(k)]
    assert len(changed) == 7
    assert {c[0] for c in changed} == {'223fz:32616181358:lot1'}
    fields = {c[1] for c in changed}
    assert fields == {'contract_price', 'contract_no', 'equipment_only_price',
                      'contract_date', 'bid', 'winner', 'source_urls'}
    row = next(x for x in b['items'] if x['id'] == '223fz:32616181358:lot1')
    assert row['winner'] == 'ООО «ЭКСПЕРТ ГРУПП»'
    assert row['contract_price'] == row['equipment_only_price'] == '3050000.00'
    assert row['signed_supplier_verified'] is False
    assert row['contract_signatory'] == '' and row['paid_amount'] == ''
    assert any(s['sha'].startswith('92874d09') for s in row['source_urls'])


def test_v8_audit_and_render():
    a = json.loads((DOC / 'ARVECTUM_FGI_PQ_FIELD_AUDIT_20261031_v8.json').read_text())
    assert a['field_coverage']['winner'] == 5
    assert a['field_coverage']['contract_price'] == 11
    assert a['field_coverage']['equipment_only_price'] == 2
    d = json.loads((ROOT / 'fgi_client_deck_snapshot_20261031_v8.json').read_text())
    html, pages = render(d, 'ru')
    assert pages == 256 and 'ЭКСПЕРТ ГРУПП' in html
    reto = html.split('id="case-27"')[1].split('</section>')[0]
    assert '3 050 000,00 ₽' in reto
