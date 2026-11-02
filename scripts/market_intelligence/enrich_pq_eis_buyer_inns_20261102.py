"""Four EIS first-party 223-FZ buyer INNs, null-only, atomic CAS."""
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

CASES = (
    ('32616120582', '7802312751', 'epc',
     '20261102T154028711965Z-280f894d-7ce5b63386ccbefb.bin',
     '7ce5b63386ccbefbc100901b5182e2763f776003e3425447ce27b7c22989ba7c'),
    ('32615969197', '0277071467', 'design',
     '20261102T154028681678Z-6c0891b4-ed5581394527cc38.bin',
     'ed5581394527cc38ab45b5215a889328ce0571aa32ca793f652b1b166eadfa44'),
    ('32616435269', '2460069527', 'supply',
     '20261102T154028660953Z-e37b6b8a-e2eed0f64be467b8.bin',
     'e2eed0f64be467b84892e18a55db3517340188ef0ffca7bff0416c22ca9f8543'),
    ('32616280467', '6450925977', 'design',
     '20261102T154028645303Z-dfb92577-87f948cd4282a6f8.bin',
     '87f948cd4282a6f8e48dbee05e3f1e55cc975b39242fc8a88f2ed713bad7d818'),
)
KEY = 'eis_buyer_inn_20261102'

def proof(case):
    n, inn, _, name, sha = case
    cid = f'223fz:{n}:lot1'
    url = (f'https://zakupki.gov.ru/epz/order/notice/notice223/'
           f'common-info.html?regNumber={n}')
    root = ROOT.resolve(strict=True)
    if root != Path('/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live'):
        raise RuntimeError('Internal APFS only')
    rel = Path('captures') / f'223fz_{n}_lot1' / name
    p = (root / rel).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or not 10000 < p.stat().st_size < 1000000:
        raise ValueError('Unsafe original')
    b = p.read_bytes()
    r = json.loads(Path(str(p)+'.json').read_text())
    quote = f'ИНН {inn} КПП'
    if (hashlib.sha256(b).hexdigest() != sha or r.get('sha256') != sha
        or r.get('case_id') != cid or r.get('source_url') != url
        or r.get('relative_file') != rel.as_posix() or r.get('http_status') != 200
        or r.get('bytes') != len(b) or n.encode() not in b):
        raise ValueError('Original SHA/identity/receipt mismatch')
    parser = Text()
    parser.feed(b.decode('utf-8', 'replace'))
    normalized = ' '.join(' '.join(parser.parts).replace('\u00a0', ' ').split())
    if (quote not in normalized or 'Наименование организации' not in normalized
            or n not in normalized):
        raise ValueError('Original SHA/identity/organizer/receipt mismatch')
    return {'url':url,'sha256':sha,'exact_original_quote':quote,'relative_file':rel.as_posix(),'role':'buyer_not_supplier'}

def validate(case,row):
    n,inn,scope,_,_ = case
    cid = f'223fz:{n}:lot1'
    d = row['data']
    if (row['id'] != cid or row['owner'] != 'tender-agent'
        or d.get('canonical_id') != cid or d.get('procedure_id') != n
        or d.get('scope') != scope or d.get('customer',{}).get('inn') != inn
        or d.get('buyer_inn') is not None or digest(d) != row['hash']
        or KEY in row['meta']):
        raise RuntimeError('Owner/identity/old-null/CAS conflict')

def apply(items,before):
    sql = ['BEGIN ISOLATION LEVEL SERIALIZABLE;',
           "SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';",
           f"SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));",
           'LOCK TABLE dp_resources, dp_records IN SHARE ROW EXCLUSIVE MODE;',
           f"""DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}')<>{before['rows']}
THEN RAISE EXCEPTION 'PQ owner/count conflict'; END IF; END $g$;"""]
    prepared = []
    for case,row,source in items:
        n,inn,_,_,_ = case
        cid = f'223fz:{n}:lot1'
        data = {**row['data'],'buyer_inn':inn,
                'evidence':[*row['data'].get('evidence',[]),
                            {'url':source['url'],'sha256':source['sha256'],
                             'source_tier':'first_party_eis_notice_buyer',
                             'excerpt':source['exact_original_quote']}]}
        h = digest(data)
        meta = {**row['meta'],'source_content_hash':h,
                KEY:{'field':'buyer_inn','value':inn,'source':source,
                     'previous_hash':row['hash'],'previous_revision':row['rev'],
                     'signed_supplier_verified':False,'paid_sale_verified':False}}
        absent = "((d.data->'buyer_inn') IS NULL OR (d.data->'buyer_inn')='null'::jsonb)"
        sql.extend([
            f"""DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d
JOIN dp_resources r USING(resource_id) WHERE r.collection_id='{COL}'
AND r.external_id='{cid}' AND r.content_hash='{row['hash']}'
AND d.revision={row['rev']} AND {absent})<>1
THEN RAISE EXCEPTION 'PQ old-null CAS {cid}'; END IF; END $g$;""",
            f"""UPDATE dp_records d SET data={js(data)},metadata={js(meta)},
revision=revision+1,updated_at=now() FROM dp_resources r
WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{cid}' AND r.content_hash='{row['hash']}'
AND d.revision={row['rev']} AND {absent};""",
            f"""UPDATE dp_resources SET content_hash='{h}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{cid}' AND content_hash='{row['hash']}';""",
            f"""DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{cid}' AND r.content_hash='{h}'
AND d.revision={row['rev']+1} AND d.data->>'buyer_inn'='{inn}'
AND d.metadata->'{KEY}'->'source'->>'sha256'='{source['sha256']}')<>1
THEN RAISE EXCEPTION 'PQ postwrite CAS {cid}'; END IF; END $g$;"""
        ])
        prepared.append((cid,inn,h,row['rev']+1,source['sha256']))
    psql('\n'.join([*sql,'COMMIT;']))
    after = snapshot()
    if before != after:
        raise RuntimeError('Corpus counts unexpectedly changed')
    results = []
    for cid,inn,h,rev,sha in prepared:
        actual = get_row(cid)
        if (actual['hash'] != h or actual['rev'] != rev
            or actual['data'].get('buyer_inn') != inn):
            raise RuntimeError('Postcommit record/hash readback mismatch')
        results.append({'id':cid,'buyer_inn':inn,'source_sha256':sha,'new_hash':h})
    return {'before':before,'after':after,'results':results,
            'new_verified_fields':len(results),'new_unique_lots':0,
            'new_signed_suppliers':0,'new_paid_sales':0}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apply',action='store_true')
    p.add_argument('--backup-manifest',type=Path)
    p.add_argument('--receipt',type=Path)
    args = p.parse_args()
    before = snapshot()
    items = []
    for case in CASES:
        source = proof(case)
        row = get_row(f'223fz:{case[0]}:lot1')
        validate(case,row)
        items.append((case,row,source))
    if not args.apply:
        print(json.dumps({'mode':'dry_run','before':before,
                          'cases':[x[2] for x in items]},ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError('New full backup manifest and unique receipt required')
    gate = subprocess.run([sys.executable,'-m','scripts.market_intelligence.verify_internal_runtime'],
                          capture_output=True,text=True,check=True,timeout=60)
    if json.loads(gate.stdout)['status'] != 'pass':
        raise RuntimeError('Internal APFS preflight blocked')
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC)-datetime.fromisoformat(backup['created_at_utc'])).total_seconds()
    if backup.get('pg_restore_list_verified') is not True or not 0 <= age <= 1800:
        raise RuntimeError('Fresh SHA+pg_restore checked full backup required')
    result = apply(items,before)
    result['backup_sha256'] = backup['sha256']
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    with args.receipt.open('x',encoding='utf8') as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False))

if __name__ == '__main__':
    main()
