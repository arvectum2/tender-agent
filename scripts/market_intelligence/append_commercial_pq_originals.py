"""Append SHA-verified commercial cards as unreviewed, non-core research leads."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from scripts.market_intelligence.append_b2b_original_card import Visible
from scripts.market_intelligence.append_pq_delta_20261029 import (
    ROOT,
    insert,
    snapshot,
    verified_backup,
)


def stage(manifest: Path, root: Path = ROOT) -> tuple[list[dict], dict]:
    m = json.loads(manifest.read_text())
    if m.get('schema_version') != 'pq-commercial-primary-incremental/1' or not 1 <= len(m['cases']) <= 10:
        raise ValueError('Bad manifest')
    root = root.resolve(strict=True)
    rows, seen = [], set()
    for c in m['cases']:
        cid = c['canonical_id']
        if not re.fullmatch(r'commercial:[0-9]{5,10}:lot1', cid) or cid in seen:
            raise ValueError('Bad or duplicate canonical ID')
        number = cid.split(':')[1]
        u = urlsplit(c['source_url'])
        if (u.scheme != 'https' or u.hostname != 'www.b2b-center.ru' or u.query or u.fragment
                or u.username or u.password or not re.fullmatch(
                    rf'/(?:market|app/market-next)/[a-z0-9-]+/tender-{number}/', u.path)):
            raise ValueError('Non-first-party URL')
        rel = Path(c['private_source_relative'])
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Unsafe relative source path')
        f = (root / rel).resolve(strict=True)
        if root not in f.parents or f.is_symlink() or not f.is_file():
            raise ValueError('Unsafe original')
        raw = f.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if not 1000 <= len(raw) <= 2_000_000 or sha != c['sha256'] or len(raw) != c['bytes']:
            raise ValueError('Source hash/size drift')
        parser = Visible()
        parser.feed(raw.decode('utf8', errors='replace'))
        visible = ' '.join(' '.join(parser.parts).split())
        quotes = c['exact_source_quotes']
        if not 3 <= len(quotes) <= 12 or not all(q in visible for q in quotes):
            raise ValueError('Source does not support exact quotes')
        if (c['technical_voltage_kv'] is not None or c['signed_supplier_verified'] is not False
                or c['paid_verified'] is not False or c['market_scope'] != 'voltage_unverified_not_core_6_35kv'
                or c['status'] not in {'retender_active', 'accepting_bids'}):
            raise ValueError('Unsupported sale/core promotion')
        rec = {'canonical_id': cid, 'procedure_id': number, 'family': c['family'],
               'scope': c['scope'], 'market_scope': c['market_scope'], 'procurement_regime': 'commercial',
               'platform': 'B2B-Center', 'publication_date': c['publication_date'],
               'customer': {'name': c['buyer']}, 'status': c['status'], 'description': c['description'],
               'technical_voltage_kv': None, 'nmck_rub': None, 'listed_price_rub': c.get('listed_price_rub'),
               'listed_price_type': c.get('listed_price_type'), 'supplier_verified': False,
               'signed_supplier_verified': False, 'paid_verified': False, 'realized_equipment_revenue_rub': None,
               'evidence': [{'url': c['source_url'], 'source_tier': 'primary_platform_original_public_card',
                             'sha256': sha, 'verbatim_quotes': quotes}]}
        full = hashlib.sha256(cid.encode()).hexdigest()
        digest = hashlib.sha256(json.dumps(rec, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        meta = {'data_version': 'commercial_source_bound_20261029', 'procurement_id': cid,
                'procedure_id': number, 'regime': 'commercial', 'family': c['family'], 'scope': c['scope'],
                'market_scope': c['market_scope'], 'status': c['status'], 'source_urls': [c['source_url']],
                'source_tiers': ['primary_platform_original_public_card'], 'source_original_sha256': [sha],
                'research_not_market_population': True, 'winning_supplier_only_if_verified': None}
        rows.append({'cid': cid, 'id': full[:48], 'uri': 'urn:arvectum:pq:procurement:' + full,
                     'hash': digest, 'record': rec, 'metadata': meta,
                     'record_metadata': {'research_version': meta['data_version'], 'source_content_hash': digest,
                                         'source_evidence_urls': [c['source_url']]}})
        seen.add(cid)
    return rows, m


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--backup-manifest', type=Path)
    p.add_argument('--receipt', type=Path)
    a = p.parse_args()
    rows, m = stage(a.manifest)
    before = snapshot()
    if any(before[k] != m['base_db_expected_records'] for k in ('rows', 'unique', 'records')):
        raise RuntimeError('DB count drift')
    if not a.apply:
        print(json.dumps({'mode': 'dry_run', 'before': before, 'ids': [r['cid'] for r in rows]}))
        return
    if not a.backup_manifest or not a.receipt or a.receipt.exists():
        raise RuntimeError('New backup and unused receipt path required')
    backup = verified_backup(a.backup_manifest)
    result = insert(rows, before['rows'])
    receipt = {'schema_version': 'pq-commercial-original-import/1', 'before': before, **result,
               'backup_sha256': backup['sha256'], 'source_manifest_sha256': hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
               'new_unique_lots': len(rows), 'verified_strict_6_35kv_new_lots': 0,
               'new_signed_suppliers': 0, 'new_verified_equipment_sales_rub': 0}
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    a.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
