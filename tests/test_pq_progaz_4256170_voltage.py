"""Offline source and fail-closed CAS tests for Progaz 10kV enrichment."""
from copy import deepcopy

import pytest

from scripts.market_intelligence import enrich_pq_progaz_4256170_voltage as mod
from scripts.market_intelligence.enrich_pq_missing_field import digest


def row():
    data = {'canonical_id': mod.CID, 'procedure_id': '4256170', 'scope': 'supply',
            'quantity': 2, 'publication_date': '2025-12-01',
            'customer': {'inn': '9709099564'}, 'equipment_voltage_kv': None,
            'evidence': [{'url': 'https://zakupki.kontur.ru/4256170_4'}]}
    return {'id': mod.CID, 'owner': 'tender-agent', 'data': data,
            'hash': digest(data), 'rev': 2, 'meta': {}}


def test_original_and_null_only_enrichment():
    source = mod.verified_original()
    assert source['sha256'] == mod.SHA
    r = row()
    mod.validate(r)
    d, meta = mod.updated(r, source)
    assert d['equipment_voltage_kv'] == '10'
    assert d['evidence'][0] == r['data']['evidence'][0]
    assert d['evidence'][-1]['sha256'] == mod.SHA
    assert meta[mod.META_KEY]['old_hash'] == r['hash']


@pytest.mark.parametrize('key,value', [('equipment_voltage_kv', '6'),
                                      ('quantity', 3), ('scope', 'design')])
def test_conflicts_fail_closed(key, value):
    r = row()
    r['data'][key] = value
    r['hash'] = digest(r['data'])
    with pytest.raises(RuntimeError):
        mod.validate(r)


def test_hash_drift_fails_closed():
    r = deepcopy(row())
    r['hash'] = '0' * 64
    with pytest.raises(RuntimeError):
        mod.validate(r)
