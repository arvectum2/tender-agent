"""SHA-verified Rosseti protocols, null-only PQ research field CAS."""
import argparse
import hashlib
import io
import json
import subprocess
import sys
import zipfile
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
from scripts.market_intelligence.enrich_pq_docx_fields import docx_text
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

KEY = 'roseltorg_commission_20261101'
CASES = [
    {'cid': '223fz:32616433248:lot1', 'nmck': '56330673.93',
         'file': '20261101T123004463050Z-a98065de-98062c8f6bb47d17.bin',
         'sha': '98062c8f6bb47d177c7630374a8f57193dcf4177e7fd37f3204cf140de05de4e',
         'url': 'https://rosseti.roseltorg.ru/file/get/t/ProtocolFiles/id/298084/user/-1/name/%D0%9F%D1%80%D0%BE%D1%82%D0%BE%D0%BA%D0%BE%D0%BB_3_%D0%B8%D1%82%D0%BE%D0%B3%D0%B8_5147.zip',
         'member': 'Протокол 3 итоги_5147.docx',
         'quotes': ['32616433248','Дата подписания Протокола: 19.10.2026',
                 '56 330 673,93','подана только одна заявка','предлагается заключить договор'],
         'fields': {'bid':'56330673.93','protocol_signed_date':'2026-10-19',
                 'protocol_participant_count':1,
                 'protocol_status_note':'Итоговый протокол №3: одна анонимная заявка №1 на 56 330 673,93 руб.; закупка признана несостоявшейся; комиссия предлагает договор и преддоговорные переговоры. Подписанный поставщик, оплата и цена одной УКРМ не подтверждены.'}},
    {'cid': '223fz:32616497692:lot1', 'nmck': '79101498.40',
         'file': '20261101T123037102187Z-9ef3b178-2f5ad8ba337f60c1.bin',
         'sha': '2f5ad8ba337f60c1e50cb42bed4c6d420be608619f533c51850448db549ddd97',
         'url': 'https://rosseti.roseltorg.ru/file/get/t/ProtocolFiles/id/299297/user/-1/name/%D0%9F%D1%80%D0%BE%D1%82%D0%BE%D0%BA%D0%BE%D0%BB_2_%D1%80%D0%B0%D1%81%D1%81%D0%BC_%D0%BF%D0%B5%D1%80%D0%B5%D1%82%D0%BE%D1%80%D0%B6%D0%BA%D0%B0_5237.zip',
         'member': 'Протокол 2 рассм+переторжка_5237.docx',
         'quotes': ['32616497692','Дата подписания Протокола: 29. 10 .2026',
                 'было по дано 1 заявка','П ровести процедуру переторжки','79 101 498,40'],
         'fields': {'protocol_signed_date':'2026-10-29','protocol_participant_count':1,
                 'protocol_status_note':'Протокол №2: одна анонимная заявка №1 допущена к переторжке. Итоговый победитель, подписанный поставщик и оплата не подтверждены.'}},
]

def proof(case):
    root = ROOT.resolve(strict=True)
    if root != Path('/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live'):
        raise ValueError('Internal APFS required')
    rel = Path('captures') / case['cid'].replace(':','_') / case['file']
    path = (root / rel).resolve(strict=True)
    if root not in path.parents or path.is_symlink() or not 1000 < path.stat().st_size < 5_000_000:
        raise ValueError('Unsafe source')
    raw = path.read_bytes()
    receipt = json.loads(Path(str(path)+'.json').read_text())
    if (hashlib.sha256(raw).hexdigest() != case['sha'] or receipt.get('sha256') != case['sha']
        or receipt.get('case_id') != case['cid'] or receipt.get('relative_file') != rel.as_posix()
        or receipt.get('source_url') != case['url'] or receipt.get('http_status') != 200
        or receipt.get('content_type') != 'application/zip'):
        raise ValueError('SHA/receipt/identity mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist()
        if (len(infos)>20 or len({i.filename for i in infos})!=len(infos)
            or any(i.file_size>3_000_000 or i.file_size>max(1,i.compress_size)*250
                   or i.filename.startswith('/') or '..' in Path(i.filename).parts for i in infos)
            or sum(i.filename==case['member'] for i in infos)!=1):
            raise ValueError('Unsafe ZIP members')
        text=docx_text(z.read(case['member']))
    if not all(q in text for q in case['quotes']):
        raise ValueError('Protocol does not prove verbatim quotes')
    return {'url':case['url'],'sha256':case['sha'],'relative_file':rel.as_posix(),
            'quotes':case['quotes'],'role':'anonymous_bidder_not_signed_supplier'}

def prepare(case,row,source):
    cid=case['cid']; d=row['data']
    if (row['id']!=cid or row['owner']!='tender-agent'
        or d.get('canonical_id')!=cid or d.get('procedure_id')!=cid.split(':')[1]
        or d.get('scope')!='epc' or d.get('customer',{}).get('inn')!='7802312751'
        or d.get('nmck_rub')!=case['nmck'] or digest(d)!=row['hash']
        or KEY in row['meta'] or any(d.get(k) is not None for k in case['fields'] )
        or d.get('winner') is not None or d.get('contract_signatory') is not None):
        raise RuntimeError('Wrong owner/identity/old-null/role')
    fields=dict(case['fields'])
    if cid=='223fz:32616497692:lot1':
        if d.get('source_urls') is not None:
            raise RuntimeError('Existing source URLs cannot be overwritten')
        fields['source_urls']=[{'url':source['url'],'sha':source['sha256'],
                               'tier':'first_party_commission_protocol'}]
    data={**d,**fields,'evidence':[*d.get('evidence',[]),
        {'url':source['url'],'sha256':source['sha256'],
         'source_tier':'first_party_commission_protocol',
         'excerpt':'; '.join(source['quotes'][:3])}]}
    h=digest(data)
    meta={**row['meta'],'source_content_hash':h,KEY:{'fields':fields,'proof':source,
        'previous_hash':row['hash'],'previous_revision':row['rev'],
        'signed_supplier_verified':False,'paid_sale_verified':False}}
    return data,meta,h,fields

def apply(items,before):
    sql=['BEGIN ISOLATION LEVEL SERIALIZABLE;',
         "SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';",
         f"SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));",
         'LOCK TABLE dp_resources,dp_records IN SHARE ROW EXCLUSIVE MODE;',
         f"""DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}')<>{before['rows']}
THEN RAISE EXCEPTION 'PQ owner/count conflict';END IF;END $g$;"""]
    prepared=[]
    for case,row,source in items:
        cid=case['cid'];data,meta,h,fields=prepare(case,row,source)
        absent=' AND '.join(f"((d.data->'{k}') IS NULL OR (d.data->'{k}')='null'::jsonb)" for k in fields)
        sql.extend([
          f"""DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d JOIN dp_resources r
USING(resource_id) WHERE r.collection_id='{COL}' AND r.external_id='{cid}'
AND r.content_hash='{row['hash']}' AND d.revision={row['rev']} AND {absent})<>1
THEN RAISE EXCEPTION 'PQ old-null CAS conflict {cid}';END IF;END $g$;""",
          f"""UPDATE dp_records d SET data={js(data)},metadata={js(meta)},
revision=revision+1,updated_at=now() FROM dp_resources r WHERE d.resource_id=r.resource_id
AND r.collection_id='{COL}' AND r.external_id='{cid}' AND r.content_hash='{row['hash']}'
AND d.revision={row['rev']} AND {absent};""",
          f"""UPDATE dp_resources SET content_hash='{h}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{cid}' AND content_hash='{row['hash']}';""",
          f"""DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d JOIN dp_resources r
USING(resource_id) WHERE r.collection_id='{COL}' AND r.external_id='{cid}'
AND r.content_hash='{h}' AND d.revision={row['rev']+1}
AND d.metadata->'{KEY}'->'proof'->>'sha256'='{source['sha256']}')<>1
THEN RAISE EXCEPTION 'PQ postwrite CAS conflict {cid}';END IF;END $g$;"""
        ])
        prepared.append((cid,h,row['rev']+1,fields,source['sha256']))
    psql('\n'.join([*sql,'COMMIT;']))
    after=snapshot()
    if before!=after:raise RuntimeError('Corpus count changed')
    results=[]
    for cid,h,rev,fields,sha in prepared:
        actual=get_row(cid)
        if (actual['hash']!=h or actual['rev']!=rev
            or any(actual['data'].get(k)!=v for k,v in fields.items())):
            raise RuntimeError('Postcommit record/hash mismatch')
        results.append({'id':cid,'new_fields':fields,'source_sha256':sha,'new_hash':h})
    return {'before':before,'after':after,'results':results,
            'new_verified_fields':sum(len(x['new_fields']) for x in results),
            'new_unique_lots':0,'new_named_winners':0,'new_signed_suppliers':0,'new_paid_sales':0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--apply',action='store_true')
    p.add_argument('--backup-manifest',type=Path)
    p.add_argument('--receipt',type=Path)
    a=p.parse_args()
    before=snapshot()
    items=[(c,get_row(c['cid']),proof(c)) for c in CASES]
    for c,row,source in items:prepare(c,row,source)
    if not a.apply:
        print(json.dumps({'mode':'dry_run','before':before,'cases':[
            {'id':c['cid'],'fields':list(prepare(c,row,source)[3]),
             'source_sha256':source['sha256']} for c,row,source in items]},ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError('Fresh backup and receipt required')
    gate=subprocess.run([sys.executable,'-m','scripts.market_intelligence.verify_internal_runtime'],
                        capture_output=True,text=True,check=True,timeout=60)
    if json.loads(gate.stdout)['status']!='pass':raise RuntimeError('Acceptance blocked')
    backup=verified_backup(a.backup_manifest)
    age=(datetime.now(UTC)-datetime.fromisoformat(backup['created_at_utc'])).total_seconds()
    if backup.get('pg_restore_list_verified') is not True or not 0<=age<=1800:
        raise RuntimeError('Fresh full SHA/pg_restore backup required')
    result=apply(items,before)
    result['backup_sha256']=backup['sha256']
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    with a.receipt.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
