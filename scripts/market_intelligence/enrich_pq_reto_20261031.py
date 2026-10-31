"""SHA-bound EIS signed capacitor contract + RAD winner; supplier remains unknown."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from html.parser import HTMLParser
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

CID = '223fz:32616181358:lot1'
NUM = '57724646338260000460000'
SOURCES = [
 ('captures/223fz_32616181358_lot1/20261031T033153506457Z-7debd590-e887daa8160e963e.bin',
  'e887daa8160e963e2bea1b9664ff5cdd929b87a08510d5bbe1aed70dd0b995b2',
  f'https://zakupki.gov.ru/epz/contractfz223/printForm/view.html?reestrNumber={NUM}'),
 ('captures/223fz_32616181358_lot1/20261031T033229533085Z-1b7133af-92874d098feb7dc6.bin',
  '92874d098feb7dc6c283bd7b66c5218e11e472f27eddffc75edd6613fb5b21ef',
  'https://tender.lot-online.ru/etp/downloadppf?uuid=dbfile19718u80000pvkg89is0k0tsd4'),
]
FIELDS = {'commission_winner_name':'ООО «ЭКСПЕРТ ГРУПП»',
          'commission_winner_inn':'7720494275', 'commission_bid_rub':'3050000.00',
          'contract_registered_price_rub':'3050000.00', 'contract_registry_number':NUM,
          'contract_register_date':'2026-08-19',
          'pq_equipment_only_contract_rub':'3050000.00'}

class T(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self,t,a):
        if t in ('script','style'):self.skip+=1
    def handle_endtag(self,t):
        if t in ('script','style'):self.skip-=1
    def handle_data(self,v):
        if not self.skip and v.strip():self.parts.append(v.strip())

def validate_texts(html,protocol):
    h=' '.join(html.split()).replace('\xa0',' ')
    for s in (NUM,'Номер договора: № 060-26-Р',
              'Дата заключения договора: 19.08.2026',
              'Извещение о закупке: №32616181358','Цена договора: 3 050 000.00',
              'КЭПФ-12-450-2УХЛ1','КЭПФ-12-600-2УХЛ1',
              '5, Штука 292 000.00','5, Штука 318 000.00'):
        if s not in h:raise ValueError('EIS original quote absent: '+s)
    if 5*292000+5*318000!=3050000:raise ValueError('price allocation')
    p=' '.join(protocol.split()).replace('\xa0',' ')
    if (not re.search(r'Признать победителем запроса котировок.*?ООО «ЭКСПЕРТ ГРУПП», ИНН:\s*7720494275',p)
            or '3 050 000,00' not in p or 'Протокол № 186-2' not in p):
        raise ValueError('RAD original winner quote absent')

def proof():
    root=ROOT.resolve(strict=True)
    if root!=Path('/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live'):
        raise ValueError('internal APFS only')
    files=[]
    for rel,sha,url in SOURCES:
        p=(root/rel).resolve(strict=True)
        if root not in p.parents or p.is_symlink() or p.stat().st_size>1000000:
            raise ValueError('unsafe source')
        raw=p.read_bytes();m=json.loads(Path(str(p)+'.json').read_text())
        if (hashlib.sha256(raw).hexdigest()!=sha or m.get('sha256')!=sha
            or m.get('relative_file')!=rel or m.get('source_url')!=url
            or m.get('case_id')!=CID or m.get('http_status')!=200
            or m.get('bytes')!=len(raw)):raise ValueError('SHA/receipt mismatch')
        files.append((p,raw))
    t=T();t.feed(files[0][1].decode('utf-8','replace'))
    pdf=subprocess.run(['pdftotext','-layout',str(files[1][0]),'-'],
                       capture_output=True,text=True,check=True,timeout=15)
    validate_texts(' '.join(t.parts),pdf.stdout)
    return {'sources':[{'url':u,'sha256':s} for _,s,u in SOURCES],
            'role':'commission_winner_not_signed_supplier',
            'signed_supplier_verified':False,'payment_verified':False,
            'equipment_allocation':'ten_capacitor_items_only_not_complete_BSK'}

def validate(r):
    d=r['data']
    if (r['id']!=CID or r['owner']!='tender-agent' or d.get('canonical_id')!=CID
        or d.get('procedure_id')!='32616181358' or d.get('scope')!='signed_equipment_supply'
        or d.get('actual_signed_contract_price_rub')!='3050000.00'
        or d.get('registered_contract_number')!=NUM
        or d.get('registered_signed_contract_verified') is not True
        or d.get('supplier_verified') is not False or d.get('paid_verified') is not False
        or digest(d)!=r['hash'] or any(d.get(k) is not None for k in FIELDS)
        or 'reto_field_enrichment' in r['meta']):raise RuntimeError('CAS/owner/source identity blocked')

def write(r,before,source):
    validate(r)
    d={**r['data'],**FIELDS}
    d['evidence']=[*r['data']['evidence'],*({'url':s['url'],'sha256':s['sha256'],
                   'source_tier':'first_party_original','excerpt':'Договор 060-26-Р / Протокол 186-2'}
                   for s in source['sources'])]
    new_hash=digest(d)
    meta={**r['meta'],'source_content_hash':new_hash,
          'reto_field_enrichment':{**source,'fields':FIELDS,'previous_hash':r['hash'],
                                   'previous_revision':r['rev']}}
    absent=' AND '.join(f"(d.data->'{k}') IS NULL" for k in FIELDS)
    present=' AND '.join(f"d.data->'{k}'={js(v)}" for k,v in FIELDS.items())
    sql=f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s';SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources,dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{r['hash']}'
AND d.revision={r['rev']} AND {absent})<>1
THEN RAISE EXCEPTION 'RETO CAS/count mismatch';END IF;END $g$;
UPDATE dp_records d SET data={js(d)},metadata={js(meta)},revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{r['hash']}'
AND d.revision={r['rev']} AND {absent};
UPDATE dp_resources SET content_hash='{new_hash}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{r['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{new_hash}'
AND d.revision={r['rev']+1} AND {present}
AND d.metadata->'reto_field_enrichment'->'sources'->1->>'sha256'='{SOURCES[1][1]}')<>1
THEN RAISE EXCEPTION 'RETO postwrite mismatch';END IF;END $g$;
COMMIT;"""
    psql(sql)
    after=snapshot();actual=get_row(CID)
    if (before!=after or actual['hash']!=new_hash or actual['rev']!=r['rev']+1
        or any(actual['data'].get(k)!=v for k,v in FIELDS.items())):
        raise RuntimeError('postwrite readback mismatch')
    return {'case':CID,'before':before,'after':after,'fields':FIELDS,
            'new_verified_fields':len(FIELDS),'new_hash':new_hash,'source':source}

def main():
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true')
    a.add_argument('--backup-manifest',type=Path);a.add_argument('--receipt',type=Path)
    args=a.parse_args();source=proof();before=snapshot();r=get_row(CID);validate(r)
    if not args.apply:
        print(json.dumps({'mode':'dry_run','case':CID,'fields':FIELDS,'before':before,
                          'sources':source},ensure_ascii=False));return
    if not args.backup_manifest or not args.receipt:raise RuntimeError('backup/receipt required')
    gate=subprocess.run([sys.executable,'-m','scripts.market_intelligence.verify_internal_runtime'],
                        capture_output=True,text=True,check=True,timeout=60)
    if json.loads(gate.stdout)['status']!='pass':raise RuntimeError('acceptance blocked')
    backup=verified_backup(args.backup_manifest)
    age=(datetime.now(UTC)-datetime.fromisoformat(backup['created_at_utc'])).total_seconds()
    if backup.get('pg_restore_list_verified') is not True or not 0<=age<=1800:
        raise RuntimeError('fresh full backup required')
    result=write(r,before,source);result['backup_sha256']=backup['sha256']
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    with args.receipt.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
