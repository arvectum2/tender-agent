"""Source-bound commercial research lead guardrails (no live database)."""
import hashlib
import json

import pytest

from scripts.market_intelligence.append_commercial_pq_originals import stage


def test_primary_commercial_card_is_not_promoted_to_core(tmp_path):
    root = tmp_path / 'runtime'
    root.mkdir()
    f = root / 'original.html'
    raw = ('<html><body>№ 1234567 Поставка УКРМ '
           'АО "ТАНДЕР" Переторжка' + '<p>Дополнительные сведения</p>' * 100 + '</body></html>').encode()
    f.write_bytes(raw)
    case = {'canonical_id': 'commercial:1234567:lot1',
            'source_url': 'https://www.b2b-center.ru/market/test/tender-1234567/',
            'private_source_relative': 'original.html', 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'exact_source_quotes': ['№ 1234567', 'Поставка УКРМ', 'Переторжка'],
            'technical_voltage_kv': None, 'signed_supplier_verified': False,
            'paid_verified': False, 'market_scope': 'voltage_unverified_not_core_6_35kv',
            'status': 'retender_active', 'family': 'ukrm', 'scope': 'mixed_supply_install_pnr',
            'publication_date': '2026-10-29', 'buyer': 'АО «Тандер»',
            'description': 'Поставка УКРМ'}
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'schema_version': 'pq-commercial-primary-incremental/1',
                                    'cases': [case]}))
    rows, _ = stage(manifest, root)
    assert rows[0]['record']['signed_supplier_verified'] is False
    assert rows[0]['record']['market_scope'] == 'voltage_unverified_not_core_6_35kv'
    case['technical_voltage_kv'] = 10
    manifest.write_text(json.dumps({'schema_version': 'pq-commercial-primary-incremental/1',
                                    'cases': [case]}))
    with pytest.raises(ValueError, match='promotion'):
        stage(manifest, root)
