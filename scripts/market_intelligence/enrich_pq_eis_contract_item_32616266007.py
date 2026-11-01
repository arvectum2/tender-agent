"""SHA-bound, null-only 223-FZ contract item CAS enrichment."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from scripts.market_intelligence.append_pq_delta_20261029 import (
    COL,
    ROOT,
    js,
    psql,
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.enrich_pq_eis_contract_32515582393 import Text
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

CID = '223fz:32616266007:lot1'
NUM = '54716016979260041190000'
FIELDS = {'contract_item_model': 'КЭПФ-12-450-2 УХЛ1', 'contract_item_quantity': 5,
          'contract_item_unit_price_rub': '132492.00',
          'contract_item_country_of_origin': 'Республика Казахстан',
          'contract_item_okpd2': '27.90.52.000'}
SOURCE = [
 ('20261101T003326625414Z-436c2c41-a2865ba18ce0e67b.bin',
  'a2865ba18ce0e67bcb45d8bf6054e1dbe13e71a15fb78287ce6cdcf273a97f74',
  f'https://zakupki.gov.ru/epz/contractfz223/card/contract-subject.html?reestrNumber={NUM}',
  ('Конденсатор КЭПФ-12-450-2 УХЛ1', '5 Штука 132 492,00', 'Республика Казахстан')),
 ('20261101T003327708575Z-d48b46b0-08b09706b512f497.bin',
  '08b09706b512f497b94941b5de857d0aabbda3eac9f1df64b4c8bd0d4e8b375c',
  f'https://zakupki.gov.ru/epz/contractfz223/printForm/view.html?reestrNumber={NUM}',
  ('Конденсатор КЭПФ-12-450-2 УХЛ1', '5, Штука 132 492.00', 'Республика Казахстан'))]


def proof():
    root = ROOT.resolve(strict=True)
    if root != Path('/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live'):
        raise RuntimeError('Internal APFS required')
    sources = []
    for name, sha, url, quotes in SOURCE:
        rel = Path('captures/223fz_32616266007_lot1') / name
        p = (root / rel).resolve(strict=True)
        if root not in p.parents or p.is_symlink() or not 32 <= p.stat().st_size <= 1000000:
            raise RuntimeError('Unsafe source path')
        raw = p.read_bytes()
        receipt = json.loads(Path(str(p) + '.json').read_text())
        if (hashlib.sha256(raw).hexdigest() != sha or receipt.get('sha256') != sha
                or receipt.get('case_id') != CID or receipt.get('source_url') != url
                or receipt.get('relative_file') != rel.as_posix() or receipt.get('http_status') != 200):
            raise RuntimeError('Source receipt mismatch')
        parser = Text(); parser.feed(raw.decode('utf8', 'replace'))
        visible = ' '.join(' '.join(parser.parts).replace('\u00a0', ' ').split())
        if not all(q in visible for q in (NUM, '1605245', *quotes)) or (name == SOURCE[1][0] and '32616266007' not in visible):
            raise RuntimeError('Identity/quote mismatch')
        sources.append({'url': url, 'sha256': sha, 'excerpt': '; '.join(quotes)})
    return sources


def validate(row):
    d = row['data']
    if (row['id'] != CID or row['owner'] != 'tender-agent'
            or d.get('canonical_id') != CID or d.get('procedure_id') != '32616266007'
            or d.get('scope') != 'capacitor_component_supply_spares'
            or d.get('customer', {}).get('inn') != '4716016979'
            or d.get('contract_registry_number') != NUM
            or d.get('contract_number') != '1605245'
            or d.get('contract_registered_price_rub') != '662460.00'
            or d.get('quantity') != 5
            or d.get('technical', {}).get('type') != 'QBANK-A CHDB-142 or equivalent'
            or d.get('signed_supplier_verified') is not False
            or d.get('paid_verified') is not False
            or digest(d) != row['hash']
            or any(d.get(k) is not None for k in FIELDS)
            or 'eis_20261101_contract_item_enrichment' in row['meta']):
        raise RuntimeError('Identity/old-null/hash CAS conflict')
    if FIELDS['contract_item_quantity'] * 132492 != 662460:
        raise RuntimeError('Price multiplication mismatch')


def prepare(row, sources):
    data = {**row['data'], **FIELDS}
    data['evidence'] = [*data.get('evidence', []), *(
        {'url': s['url'], 'sha256': s['sha256'],
         'source_tier': 'first_party_eis_registered_contract_subject',
         'excerpt': s['excerpt']} for s in sources)]
    new_hash = digest(data)
    meta = {**row['meta'], 'source_content_hash': new_hash,
            'eis_20261101_contract_item_enrichment': {
                'fields': FIELDS, 'sources': sources, 'previous_hash': row['hash'],
                'previous_revision': row['rev'], 'signed_supplier_verified': False,
                'paid_verified': False,
                'caution': 'Registry contract model differs from tender technical model; equivalence unverified.'}}
    return data, meta, new_hash


def apply(row, sources, before):
    data, meta, h = prepare(row, sources)
    nulls = ' AND '.join(f"(d.data->'{k}') IS NULL" for k in FIELDS)
    sql = f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources,dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}'
AND r.content_hash='{row['hash']}' AND d.revision={row['rev']} AND {nulls})<>1
THEN RAISE EXCEPTION 'PQ CAS/owner/count mismatch';END IF;END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{row['hash']}' AND d.revision={row['rev']} AND {nulls};
UPDATE dp_resources SET content_hash='{h}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{h}'
AND d.revision={row['rev']+1} AND d.data->>'contract_item_model'='КЭПФ-12-450-2 УХЛ1'
AND d.data->>'contract_item_quantity'='5'
AND d.metadata->'eis_20261101_contract_item_enrichment'->'sources'->0->>'sha256'='{sources[0]['sha256']}')<>1
THEN RAISE EXCEPTION 'PQ postwrite mismatch';END IF;END $g$;
COMMIT;"""
    psql(sql)
    after, actual = snapshot(), get_row(CID)
    if (before != after or actual['hash'] != h or actual['rev'] != row['rev'] + 1
            or any(actual['data'].get(k) != v for k, v in FIELDS.items())):
        raise RuntimeError('Postcommit readback mismatch')
    return {'before': before, 'after': after, 'new_unique_lots': 0,
            'new_verified_fields': len(FIELDS), 'case': CID,
            'new_hash': h, 'sources': sources}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true')
    p.add_argument('--backup-manifest', type=Path)
    p.add_argument('--receipt', type=Path)
    a = p.parse_args()
    sources = proof()
    row, before = get_row(CID), snapshot()
    validate(row)
    if not a.apply:
        print(json.dumps({'mode': 'dry_run', 'before': before,
                          'fields': FIELDS, 'sources': sources}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError('Fresh backup and receipt mandatory')
    gate = subprocess.run([sys.executable, '-m', 'scripts.market_intelligence.verify_internal_runtime'],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)['status'] != 'pass':
        raise RuntimeError('Acceptance failed')
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup['created_at_utc'])).total_seconds()
    if backup.get('pg_restore_list_verified') is not True or not 0 <= age <= 1800:
        raise RuntimeError('Fresh SHA+pg_restore backup required')
    result = apply(row, sources, before)
    result['backup_sha256'] = backup['sha256']
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open('x', encoding='utf8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
