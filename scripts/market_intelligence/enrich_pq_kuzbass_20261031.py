"""CAS P2/P3: first-party Kuzbass filter-capacitor component evidence, not signed sale."""
import argparse
import hashlib
import json
import re
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
from scripts.market_intelligence.enrich_pq_docx_fields import docx_text
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

CID='223fz:32514947144:lot1'
SOURCES=[
('20261031T133931117207Z-89b5e8f4-23f49591598c82ae.bin','23f49591598c82ae010d28a2e1373d6f567654e9c83821e1adab8635c37b589c','https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=32514947144&noticeGuid=0eed794d-6945-4586-93be-d06bd210bb97'),
('20261031T134020351814Z-295defee-5aee81a7a8dc65d4.bin','5aee81a7a8dc65d4314ba718ab7621293ca3d708448958fd22c1cd5bdeb2f94c','https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=AF7F8E3D08204DB9B1D42925DCD4F503'),
('20261031T134020599894Z-d30b773f-1f3cde0fa95d5187.bin','1f3cde0fa95d5187b707e978108553894dea2c1377ca0123b5a3d7b08a113fd8','https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=D1DC968639B14289B4AB8A32D3126996')]
WINNER='ООО «ТОРГОВЫЙ ДОМ «УСТЬ-КАМЕНОГОРСКИЙ КОНДЕНСАТОР»'
FIELDS={'equipment_voltage_kv':'12','power':'450 кВАр на конденсатор','quantity':14,
'commission_bid_rub':'3158400.00','commission_winner_name':WINNER,
'commission_protocol_number':'1/3515171','commission_protocol_date':'2025-07-04',
'technical':{'component_type':'КЭПФ-12-450-2 УХЛ1 или эквивалент','component_voltage_kv':'12',
'component_power_kvar_each':'450','component_quantity':'14','application_substation_voltage_kv':'500',
'application_site':'ПС 500 кВ Ново-Анжерская','purpose':'аварийный запас компонентов фильтра, не система PQ 6–35 кВ'}}

def proof():
 root=ROOT.resolve(strict=True)
 if root!=Path('/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live'):raise ValueError('internal APFS only')
 blobs=[];sources=[]
 for name,sha,url in SOURCES:
  rel=Path('captures/223fz_32514947144_lot1')/name
  p=(root/rel).resolve(strict=True)
  if root not in p.parents or p.is_symlink() or not 32<=p.stat().st_size<=12000000:raise ValueError('unsafe source')
  b=p.read_bytes();m=json.loads(Path(str(p)+'.json').read_text())
  if hashlib.sha256(b).hexdigest()!=sha or any((m.get('sha256')!=sha,m.get('case_id')!=CID,m.get('source_url')!=url,m.get('relative_file')!=rel.as_posix(),m.get('bytes')!=len(b),m.get('http_status')!=200)):
   raise ValueError('source receipt SHA/identity mismatch')
  blobs.append(b);sources.append({'url':url,'sha256':sha,'source_tier':'first_party_original','excerpt':'14 x КЭПФ-12-450-2, ПС 500 кВ; протокол 1/3515171, 3 158 400 руб.'})
 h=blobs[0].decode('utf8','replace');t=docx_text(blobs[1]);p=docx_text(blobs[2])
 if '32514947144' not in h or 'Поставка конденсаторов для силовых фильтров' not in h:raise ValueError('EIS identity absent')
 for q in ('ПС 500 кВ Ново-Анжерская','КЭПФ-12-450-2 УХЛ1','Напряжение, кВ - 12 ;','Мощность, квар – 450 ;'):
  if q not in t:raise ValueError('technical quote absent: '+q)
 if not re.search(r'КЭПФ-12-450-2 УХЛ1.*?Напряжение, кВ - 12 ;.*?Мощность, квар – 450 ;.*?\b14\b',t):raise ValueError('specification binding absent')
 if not all(q in re.sub(r'\s+','',p) for q in ('ПРОТОКОЛ№1/3515171','04.07.2025')):raise ValueError('protocol number/date absent')
 for q in ('32514947144',WINNER,'3 158 400,00','Победитель','признать данного участника победителем'):
  if q not in p:raise ValueError('protocol quote absent: '+q)
 return sources

def validate(row):
 d=row['data']
 if (row['id']!=CID or row['owner']!='tender-agent' or d.get('canonical_id')!=CID
  or d.get('procedure_id')!='32514947144' or d.get('scope')!='supply_components'
  or d.get('nmck_rub')!='3186960' or d.get('supplier_verified') is not False
  or d.get('signed_supplier_verified') is True or d.get('registered_signed_contract_verified') is True
  or digest(d)!=row['hash'] or any(d.get(k) is not None for k in FIELDS)
  or 'kuzbass_20261031_p2_p3' in row['meta']):raise RuntimeError('CAS/owner/old-null mismatch')

def build(row,sources):
 d={**row['data'],**FIELDS,'evidence':[*(row['data'].get('evidence') or []),*sources]}
 h=digest(d)
 meta={**row['meta'],'source_content_hash':h,'kuzbass_20261031_p2_p3':{'fields':FIELDS,
 'source_sha256':[s['sha256'] for s in sources],'previous_hash':row['hash'],
 'previous_revision':row['rev'],'commission_winner_not_signed_supplier':True,
 'application_voltage_kv':500,'paid_verified':False}}
 return d,meta,h

def write(row,before,sources):
 d,meta,h=build(row,sources)
 absent=' AND '.join(f"(d.data->>'{k}') IS NULL" for k in FIELDS)
 present=' AND '.join(f"d.data->'{k}'={js(v)}" for k,v in FIELDS.items())
 sql=f'''BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources,dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id) WHERE r.collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{row['hash']}'
AND d.revision={row['rev']} AND {absent})<>1
THEN RAISE EXCEPTION 'PQ old-null/count CAS mismatch';END IF;END $g$;
UPDATE dp_records d SET data={js(d)},metadata={js(meta)},revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{row['hash']}' AND d.revision={row['rev']} AND {absent};
UPDATE dp_resources SET content_hash='{h}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{h}'
AND d.revision={row['rev']+1} AND {present}
AND d.metadata->'kuzbass_20261031_p2_p3'->'source_sha256'->>2='{sources[2]['sha256']}')<>1
THEN RAISE EXCEPTION 'PQ postwrite CAS mismatch';END IF;END $g$;
COMMIT;'''
 psql(sql)
 after=snapshot();actual=get_row(CID)
 if before!=after or actual['hash']!=h or actual['rev']!=row['rev']+1 or any(actual['data'].get(k)!=v for k,v in FIELDS.items()):
  raise RuntimeError('Postcommit readback mismatch')
 return {'case_id':CID,'db_before':before,'db_after':after,'new_verified_fields':len(FIELDS),
         'source_shas':[s['sha256'] for s in sources],'new_hash':h,'winner_not_signed_supplier':True}

def main():
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true')
 p.add_argument('--backup-manifest',type=Path);p.add_argument('--receipt',type=Path)
 a=p.parse_args();sources=proof();row=get_row(CID);validate(row);before=snapshot()
 if not a.apply:
  print(json.dumps({'mode':'dry_run','case':CID,'db':before,'fields':FIELDS,
                    'source_shas':[s['sha256'] for s in sources]},ensure_ascii=False));return
 if not a.backup_manifest or not a.receipt:raise RuntimeError('fresh full backup and receipt required')
 gate=subprocess.run([sys.executable,'-m','scripts.market_intelligence.verify_internal_runtime'],
                     capture_output=True,text=True,check=True,timeout=60)
 if json.loads(gate.stdout)['status']!='pass':raise RuntimeError('APFS acceptance blocked')
 backup=verified_backup(a.backup_manifest)
 age=(datetime.now(UTC)-datetime.fromisoformat(backup['created_at_utc'])).total_seconds()
 if backup.get('pg_restore_list_verified') is not True or not 0<=age<=1800:raise RuntimeError('stale/unverified backup')
 result=write(row,before,sources);result['backup_sha256']=backup['sha256']
 with a.receipt.open('x',encoding='utf8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
 print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
