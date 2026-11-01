"""Portable CAS/role tests; never require the private source archive or DB."""
import copy

import pytest

from scripts.market_intelligence.enrich_pq_missing_field import digest
from scripts.market_intelligence.enrich_pq_roseltorg_commission_20261101 import (
    CASES,
    prepare,
)


def row(case):
    d = {'canonical_id': case['cid'], 'procedure_id': case['cid'].split(':')[1],
         'scope': 'epc', 'customer': {'inn': '7802312751'},
         'nmck_rub': case['nmck'], 'evidence': [], 'winner': None,
         'contract_signatory': None}
    return {'id': case['cid'], 'owner': 'tender-agent', 'hash': digest(d),
            'rev': 2, 'data': d, 'meta': {}}


def source(case):
    return {'url': case['url'], 'sha256': case['sha'], 'quotes': case['quotes']}


@pytest.mark.parametrize('case', CASES)
def test_null_only_source_bound(case):
    d, meta, h, fields = prepare(case, row(case), source(case))
    assert h == digest(d)
    assert meta['roseltorg_commission_20261101']['proof']['sha256'] == case['sha']
    assert d['evidence'][-1]['source_tier'] == 'first_party_commission_protocol'
    assert d['winner'] is None and d['contract_signatory'] is None
    assert d['protocol_participant_count'] == 1
    assert len(fields) == 4


@pytest.mark.parametrize('case', CASES)
def test_conflict_fails_closed(case):
    r = row(case)
    r['data']['protocol_signed_date'] = 'conflict'
    r['hash'] = digest(r['data'])
    with pytest.raises(RuntimeError, match='Wrong owner/identity/old-null/role'):
        prepare(case, r, source(case))
    r = row(case)
    r['data']['winner'] = 'not proven'
    r['hash'] = digest(r['data'])
    with pytest.raises(RuntimeError, match='Wrong owner/identity/old-null/role'):
        prepare(case, r, source(case))


def test_source_url_conflict_not_overwritten():
    case = CASES[1]
    r = copy.deepcopy(row(case))
    r['data']['source_urls'] = [{'url': 'existing'}]
    r['hash'] = digest(r['data'])
    with pytest.raises(RuntimeError, match='Existing source URLs'):
        prepare(case, r, source(case))
