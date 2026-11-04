"""Source-bound null-only model ratings; never attribute awarded OEM or paid sale."""
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
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

CID = 'commercial:4643332:lot1'
FIELDS = {'equipment_voltage_kv': '10.5', 'power': '150 кВАр (номинал модели; закупка не состоялась)'}
SOURCES = [
 ('20261102T033535474057Z-3612f78b-c3ab1826443946f4.bin',
  'c3ab1826443946f46da208fa412b5c344f3b13e05733298eebc511191dfcd57e',
  'https://www.b2b-center.ru/market/808-kondensator-kep3-10-5-150-3u2/tender-4643332/',
  ['КЭП3-10,5-150-3У2'], 'first_party_procurement_model'),
 ('20261102T033743214743Z-4e22b19d-cffe971868056da0.bin',
  'cffe971868056da009187f9fc0fb721627fd62181449788cd0722735c8854f73',
  'https://ukkz.com/en/catalog/capacitors/power-factor-correction-capacitors/high-voltage-power-factor-correction-capacitors.html',
  ['KEP3-10,5-150-3U2', 'rated voltage in kV', 'rated power in kvar'],
  'manufacturer_model_reference_not_awarded_oem')]


def proof(root=ROOT):
    root = Path(root).resolve(strict=True)
    if root != Path('/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live'):
        raise RuntimeError('Internal APFS required')
    out = []
    for filename, sha, url, quotes, tier in SOURCES:
        rel = Path('captures') / CID.replace(':', '_') / filename
        p = (root / rel).resolve(strict=True)
        if root not in p.parents or p.is_symlink() or not 32 <= p.stat().st_size <= 12_000_000:
            raise ValueError('Unsafe source')
        raw = p.read_bytes()
        receipt = json.loads(Path(str(p) + '.json').read_text())
        if (hashlib.sha256(raw).hexdigest() != sha or receipt['sha256'] != sha
                or receipt['case_id'] != CID or receipt['source_url'] != url
                or receipt['relative_file'] != rel.as_posix() or receipt['http_status'] != 200
                or any(q.encode('utf8') not in raw for q in quotes)):
            raise ValueError('Source SHA/quote/receipt mismatch')
        out.append({'url': url, 'sha256': sha, 'source_tier': tier,
                    'excerpt': '; '.join(quotes)})
    return out


def validate(row):
    d = row['data']
    if (row['id'] != CID or row['owner'] != 'tender-agent'
            or d.get('canonical_id') != CID or d.get('procedure_id') != '4643332'
            or d.get('scope') != 'supply' or d.get('quantity') != 1
            or d.get('customer', {}).get('inn') != '2709015787'
            or 'КЭП3-10,5-150-3У2' not in d.get('description', '')
            or digest(d) != row['hash']
            or any(d.get(k) is not None for k in FIELDS)
            or 'ukcp_model_reference_20261102' in row['meta']
            or not any(e.get('url') == SOURCES[0][2] for e in d.get('evidence', []))):
        raise RuntimeError('Old-null/identity/content CAS conflict')


def prepared(row, sources):
    data = {**row['data'], **FIELDS}
    data['evidence'] = [*data.get('evidence', []), *sources]
    new_hash = digest(data)
    meta = {**row['meta'], 'source_content_hash': new_hash,
            'ukcp_model_reference_20261102': {
                'fields': FIELDS, 'sources': sources,
                'previous_hash': row['hash'], 'previous_revision': row['rev'],
                'awarded_oem_verified': False, 'signed_supplier_verified': False,
                'paid_sale_verified': False}}
    return data, meta, new_hash


def apply(row, before, sources):
    data, meta, new_hash = prepared(row, sources)
    old_hash, rev = row['hash'], row['rev']
    sql = f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources,dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['unique']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}')<>{before['records']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{old_hash}'
AND d.revision={rev} AND (d.data->'equipment_voltage_kv') IS NULL
AND (d.data->'power') IS NULL)<>1
THEN RAISE EXCEPTION 'PQ guarded CAS/owner/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},
revision=revision+1,updated_at=now() FROM dp_resources r
WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{old_hash}'
AND d.revision={rev} AND (d.data->'equipment_voltage_kv') IS NULL
AND (d.data->'power') IS NULL;
UPDATE dp_resources SET content_hash='{new_hash}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{old_hash}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}'
AND r.content_hash='{new_hash}' AND d.revision={rev+1}
AND d.data->>'equipment_voltage_kv'='10.5'
AND d.metadata->'ukcp_model_reference_20261102'->'sources'->1->>'sha256'='{sources[1]['sha256']}')<>1
THEN RAISE EXCEPTION 'PQ postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after, actual = snapshot(), get_row(CID)
    if (before != after or actual['hash'] != new_hash or actual['rev'] != rev+1
            or any(actual['data'].get(k) != v for k,v in FIELDS.items())):
        raise RuntimeError('Postcommit readback mismatch')
    return {'case_id': CID, 'new_verified_fields': 2, 'fields': FIELDS,
            'source_shas': [s['sha256'] for s in sources], 'before': before,
            'after': after, 'new_hash': new_hash,
            'signed_supplier_verified': False, 'paid_sale_verified': False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true')
    p.add_argument('--backup-manifest', type=Path)
    p.add_argument('--receipt', type=Path)
    args = p.parse_args()
    sources, row, before = proof(), get_row(CID), snapshot()
    validate(row)
    if not args.apply:
        print(json.dumps({'mode':'dry_run','before':before,'case_id':CID,
                          'fields':FIELDS,'source_shas':[s['sha256'] for s in sources]},ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError('Fresh full backup and receipt required')
    gate = subprocess.run([sys.executable,'-m','scripts.market_intelligence.verify_internal_runtime'],
                          capture_output=True,text=True,check=True,timeout=60)
    if json.loads(gate.stdout)['status'] != 'pass':
        raise RuntimeError('Internal APFS acceptance failed')
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC)-datetime.fromisoformat(backup['created_at_utc'])).total_seconds()
    if backup.get('pg_restore_list_verified') is not True or not 0 <= age <= 1800:
        raise RuntimeError('Fresh SHA+pg_restore full backup required')
    result = apply(row,before,sources)
    result['backup_sha256'] = backup['sha256']
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    with args.receipt.open('x',encoding='utf8') as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False))


if __name__ == '__main__':
    main()
