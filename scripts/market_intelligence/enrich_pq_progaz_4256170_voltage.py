"""Null-only, first-party-SHA guarded Progaz 10 kV field enrichment."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from lxml import html

from scripts.market_intelligence.append_pq_delta_20261029 import (
    COL,
    ROOT,
    js,
    psql,
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

CID = 'commercial:4256170:lot1'
URL = 'https://www.b2b-center.ru/market/postavka-kondensatornykh-ustanovok-ukrm-10-kv-1600-kva-v-kol-ve-1/tender-4256170/'
REL = 'captures/commercial_4256170_lot1/20261102T013745693103Z-a06bffbd-71fba87b2a06c462.bin'
SHA = '71fba87b2a06c46251165c709fb5d6a0dbff953d972cb4c02e3f76bc8377d1d1'
VALUE = '10'
META_KEY = 'b2b_progaz_4256170_voltage'
INTERNAL = Path('/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live')
QUOTES = ('Тендер № 4256170', 'УКРМ-10 кВ 1600 кВА', 'УКРМ-10 кВ 50 кВА', 'Заказчики: ООО "ПРОГАЗСТРОЙ"')


def verified_original():
    root = ROOT.resolve(strict=True)
    if root != INTERNAL:
        raise RuntimeError('Internal APFS required')
    p = (root / REL).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or p.stat().st_size > 2_000_000:
        raise RuntimeError('Unsafe original')
    b = p.read_bytes()
    receipt = json.loads(Path(str(p) + '.json').read_text())
    text = ' '.join(' '.join(html.fromstring(b).itertext()).split())
    if (hashlib.sha256(b).hexdigest() != SHA or receipt.get('sha256') != SHA
            or receipt.get('source_url') != URL or receipt.get('case_id') != CID
            or receipt.get('http_status') != 200 or receipt.get('bytes') != len(b)
            or receipt.get('relative_file') != REL
            or not all(q in text for q in QUOTES)):
        raise RuntimeError('Source SHA/receipt/quotes mismatch')
    return {'url': URL, 'sha256': SHA, 'relative_file': REL, 'quotes': list(QUOTES)}


def validate(row):
    d = row['data']
    if (row['id'] != CID or row['owner'] != 'tender-agent'
            or digest(d) != row['hash'] or d.get('canonical_id') != CID
            or d.get('procedure_id') != '4256170' or d.get('scope') != 'supply'
            or d.get('quantity') != 2 or d.get('publication_date') != '2025-12-01'
            or d.get('customer', {}).get('inn') != '9709099564'
            or d.get('equipment_voltage_kv') is not None
            or d.get('voltage_kv') is not None or META_KEY in row['meta']):
        raise RuntimeError('Identity/owner/old-null/CAS blocked')


def updated(row, source):
    d = dict(row['data'])
    d['equipment_voltage_kv'] = VALUE
    d['evidence'] = [*d['evidence'], {'url': URL, 'sha256': SHA,
        'tier': 'first_party_original', 'field': 'equipment_voltage_kv',
        'value': VALUE, 'exact_quote': QUOTES[1]}]
    meta = {**row['meta'], 'source_content_hash': digest(d), META_KEY: {
        'source': source, 'field': 'equipment_voltage_kv', 'value': VALUE,
        'old_hash': row['hash'], 'old_revision': row['rev'],
        'warning': 'One bid is not a signed supplier or paid sale'}}
    return d, meta


def apply(row, before, source):
    d, meta = updated(row, source)
    new_hash = digest(d)
    where = (f"r.collection_id='{COL}' AND r.external_id='{CID}' "
             f"AND r.content_hash='{row['hash']}' AND d.revision={row['rev']} "
             "AND (d.data->'equipment_voltage_kv') IS NULL")
    sql = f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources, dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE {where})<>1 THEN RAISE EXCEPTION 'PQ prewrite CAS'; END IF; END $g$;
UPDATE dp_records d SET data={js(d)},metadata={js(meta)},revision=revision+1,
updated_at=now() FROM dp_resources r WHERE d.resource_id=r.resource_id AND {where};
UPDATE dp_resources SET content_hash='{new_hash}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{new_hash}'
AND d.revision={row['rev']+1} AND d.data->>'equipment_voltage_kv'='{VALUE}'
AND d.metadata->'{META_KEY}'->'source'->>'sha256'='{SHA}')<>1
THEN RAISE EXCEPTION 'PQ postwrite CAS'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after, got = snapshot(), get_row(CID)
    if (before != after or got['hash'] != new_hash
            or got['rev'] != row['rev'] + 1 or got['data'] != d):
        raise RuntimeError('Postwrite count/hash/readback mismatch')
    return {'case_id': CID, 'source_sha256': SHA, 'before': before,
            'after': after, 'old_hash': row['hash'], 'new_hash': new_hash,
            'new_verified_fields': 1}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true')
    p.add_argument('--backup-manifest', type=Path)
    p.add_argument('--receipt', type=Path)
    a = p.parse_args()
    source = verified_original()
    before, row = snapshot(), get_row(CID)
    validate(row)
    if not a.apply:
        print(json.dumps({'mode': 'dry_run', 'case': CID, 'before': before,
                          'source_sha256': SHA}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError('Fresh backup and new receipt required')
    gate = subprocess.run([sys.executable, '-m', 'scripts.market_intelligence.verify_internal_runtime'],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)['status'] != 'pass':
        raise RuntimeError('Acceptance blocked')
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup['created_at_utc'])).total_seconds()
    if not backup.get('pg_restore_list_verified') or not 0 <= age <= 1800:
        raise RuntimeError('Fresh verified full backup required')
    result = apply(row, before, source)
    result['backup_sha256'] = backup['sha256']
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
