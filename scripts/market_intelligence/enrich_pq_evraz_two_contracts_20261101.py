"""SHA-verified, null-only CAS: two registered mixed-work contracts, one lot."""
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

CID = '223fz:32413195287:lot1'
NUMBERS = ('54217084532240000450000', '54217084532240000460000')
FILES = (
    ('20261101T052837446587Z-0482f857-d8db0210aa94eaef.bin', 'd8db0210aa94eaef7102c4384ec188d82468a736647369daad0a253c7e5e7db4', 'https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber=32413195287', ('ИНН 4217084532', 'Капитальный ремонт УКРМ-2')),
    ('20261101T052924544883Z-bbaab290-b5c6cc09f7b2dec4.bin', 'b5c6cc09f7b2dec47682a5d63c4445d51762db3da3f74c2d31b9aa69efa7b0a2', 'https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber=' + NUMBERS[0], (NUMBERS[0], 'Извещение о закупке № 32413195287', 'Цена договора 1 043 734,03', 'Заключение договора 11.03.2024', 'Исполнение завершено')),
    ('20261101T052925180659Z-3c55961f-926bbce4fd20cb0d.bin', '926bbce4fd20cb0d264f42cd25326063131ffb73997d45706097a2953f752964', 'https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber=' + NUMBERS[1], (NUMBERS[1], 'Извещение о закупке № 32413195287', 'Цена договора 13 090 401,45', 'Заключение договора 11.03.2024', 'Исполнение завершено')),
    ('20261101T053021234648Z-0588b0af-c968b9971c26b452.bin', 'c968b9971c26b45280c5839eafb74de45487fee9abd08e5132a3a84880aedf67', 'https://zakupki.gov.ru/epz/order/notice/protocol223/printForm/view.html?protocolGuid=de3ff731-327c-4d80-bc52-aa93e75fc566&purchaseNoticeNumber=32413195287', ('Итоговый протокол', '32413195287-03', 'Заявок нет', 'Заявки отсутствуют')),
)
FIELDS = {
    'buyer_inn': '4217084532',
    'source_urls': [{'url': FILES[0][2], 'tier': 'first_party', 'sha': FILES[0][1]}],
    'registered_signed_contract_verified': True,
    'contract_registry_entries': [
        {'registry_number': n, 'signed_date': '2024-03-11', 'registered_price_rub': p,
         'registry_status': 'Исполнение завершено', 'source_sha256': FILES[i][1]}
        for i, (n, p) in enumerate(zip(NUMBERS, ('1043734.03', '13090401.45'), strict=True), 1)
    ],
    'contract_status_note': 'ЕИС: два реестровых договора от 11.03.2024 (1 043 734,03 и 13 090 401,45 руб.), оба с отметкой «Исполнение завершено». Итоговый протокол №32413195287-03: заявок нет. Победитель, подписант, оплата, доля ремонта УКРМ и стоимость оборудования отдельно не установлены; смешанные работы не считать продажей PQ.',
}


def proof():
    root = ROOT.resolve(strict=True)
    if root != Path('/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live'):
        raise RuntimeError('Internal APFS required')
    sources = []
    for name, sha, url, quotes in FILES:
        rel = Path('captures/223fz_32413195287_lot1') / name
        p = (root / rel).resolve(strict=True)
        if root not in p.parents or p.is_symlink() or not 32 <= p.stat().st_size <= 1_000_000:
            raise RuntimeError('Unsafe source')
        raw = p.read_bytes()
        receipt = json.loads(Path(str(p) + '.json').read_text())
        visible = ' '.join(' '.join(html.fromstring(raw.decode('utf-8', 'replace')).itertext()).replace('\u00a0', ' ').split())
        if (hashlib.sha256(raw).hexdigest() != sha or receipt.get('sha256') != sha
                or receipt.get('relative_file') != rel.as_posix() or receipt.get('case_id') != CID
                or receipt.get('source_url') != url or receipt.get('http_status') != 200
                or receipt.get('bytes') != len(raw) or not all(q in visible for q in quotes)):
            raise RuntimeError('Source SHA/receipt/quote mismatch: ' + name)
        sources.append({'url': url, 'sha256': sha, 'quotes': list(quotes)})
    return sources


def validate(row):
    d = row['data']
    if (row['id'] != CID or row['owner'] != 'tender-agent'
            or d.get('canonical_id') != CID or d.get('procedure_id') != '32413195287'
            or d.get('scope') != 'mixed_epc_repair_services'
            or d.get('nmck_rub') != '13892027.33' or digest(d) != row['hash']
            or any(d.get(k) is not None for k in FIELDS)
            or d.get('contract_registry_number') is not None
            or d.get('contract_registered_price_rub') is not None
            or 'evraz_dual_contract_20261101' in row['meta']):
        raise RuntimeError('Identity/owner/old-null/hash conflict')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-manifest', type=Path)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    sources = proof()
    row, before = get_row(CID), snapshot()
    validate(row)
    data = {**row['data'], **FIELDS}
    new_hash = digest(data)
    meta = {**row['meta'], 'source_content_hash': new_hash,
            'evraz_dual_contract_20261101': {
                'sources': sources, 'fields': list(FIELDS),
                'previous_hash': row['hash'], 'previous_revision': row['rev'],
                'supplier_verified': False, 'paid_verified': False,
                'pq_equipment_allocation_verified': False}}
    if not args.apply:
        print(json.dumps({'mode': 'dry_run', 'before': before,
                          'new_verified_fields': len(FIELDS), 'sources': sources}, ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError('Fresh backup and receipt required')
    gate = subprocess.run([sys.executable, '-m', 'scripts.market_intelligence.verify_internal_runtime'],
                          check=True, capture_output=True, text=True, timeout=60)
    if json.loads(gate.stdout)['status'] != 'pass':
        raise RuntimeError('Acceptance failed')
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup['created_at_utc'])).total_seconds()
    if backup.get('pg_restore_list_verified') is not True or not 0 <= age <= 1800:
        raise RuntimeError('Fresh full SHA+pg_restore backup required')
    nulls = ' AND '.join(f"((d.data->'{k}') IS NULL OR (d.data->'{k}')='null'::jsonb)" for k in FIELDS)
    where = (f"r.collection_id='{COL}' AND r.external_id='{CID}' "
             f"AND r.content_hash='{row['hash']}' AND d.revision={row['rev']} AND {nulls}")
    sql = f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources,dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id) WHERE r.collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id) WHERE {where})<>1
THEN RAISE EXCEPTION 'Evraz prewrite CAS'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND {where};
UPDATE dp_resources SET content_hash='{new_hash}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{new_hash}'
AND d.revision={row['rev']+1} AND d.data->>'buyer_inn'='4217084532'
AND d.data->>'registered_signed_contract_verified'='true'
AND jsonb_array_length(d.data->'contract_registry_entries')=2
AND d.data->'contract_registry_entries'->0->>'registry_number'='{NUMBERS[0]}'
AND d.data->'contract_registry_entries'->1->>'registry_number'='{NUMBERS[1]}'
AND d.metadata->'evraz_dual_contract_20261101'->'sources'->3->>'sha256'='{FILES[3][1]}')<>1
THEN RAISE EXCEPTION 'Evraz postwrite CAS'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after, got = snapshot(), get_row(CID)
    if (after != before or got['hash'] != new_hash or got['rev'] != row['rev'] + 1
            or got['data'] != data
            or got['meta']['evraz_dual_contract_20261101'] != meta['evraz_dual_contract_20261101']):
        raise RuntimeError('Postwrite readback mismatch')
    result = {'case': CID, 'before': before, 'after': after, 'new_unique_lots': 0,
              'new_verified_fields': len(FIELDS), 'new_signed_suppliers': 0,
              'new_paid_sales': 0, 'source_shas': [s['sha256'] for s in sources],
              'old_hash': row['hash'], 'new_hash': new_hash,
              'full_backup_sha256': backup['sha256']}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open('x', encoding='utf8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
