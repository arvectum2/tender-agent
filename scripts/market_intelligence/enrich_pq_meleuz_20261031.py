"""Verified 6.3kV UKRM contract: source-bound null-only PostgreSQL enrichment."""
import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
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
from scripts.market_intelligence.enrich_pq_eis_contract_32615966040 import Text
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

CID='223fz:32616296475:lot1'
FOLDER='captures/223fz_32616296475_lot1/'
SOURCES={
 'contract':('20261031T083806232981Z-63b41a18-51d201695c4aa972.bin','51d201695c4aa97264e17922a053ba6eca03b0032c13d7cd815dff487c9de90f','https://zakupki.gov.ru/epz/order/notice/notice223/contract/printForm/viewXml.html?contractRegistrationNumber=50263017332260000870001'),
 'card':('20261031T083806162222Z-b01feab2-f598adc6ffb6281a.bin','f598adc6ffb6281ac20b025a86a1632091d2f9851dc7c2e018e9b04514fae270','https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber=50263017332260000870000'),
 'protocol':('20261031T083806208665Z-1f80763f-b3a03bb02d5b8492.bin','b3a03bb02d5b84928e91e344de90310679189dc95e84f99d3b8cc7df989aa473','https://zakupki.gov.ru/epz/order/notice/protocol223/printForm/view.html?protocolGuid=b2199faa-ca90-4c2d-9985-66bf9a0dc70f&purchaseNoticeNumber=32616296475'),
 'technical':('20261031T083935873352Z-513b1981-ca9a840c69bce647.bin','ca9a840c69bce647287c4571b675d57f401f89a20ae3d24f3842d8e24485b781','https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=9F25836F133B4126AC928EB0AB6842B6')
}
FIELDS={
 'contract_registry_number':'50263017332260000870000',
 'contract_number':'304/26',
 'contract_signed_date':'2026-09-21',
 'contract_registered_price_rub':'3865725.99',
 'registered_signed_contract_verified':True,
 'voltage_kv':'не более 6,3 кВ (требование ТЗ)',
 'power':'не менее 500 кВАр (требование ТЗ)',
 'technology_requirement':'тиристорное и реакторное устройство с фильтром высших гармоник',
 'commission_first_place_bid_rub':'3865725.99',
 'commission_first_place_application':'79410',
}

def norm(s):return ' '.join(s.replace('\xa0',' ').split())

def proof():
 root=ROOT.resolve(strict=True)
 if root!=Path('/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live'):raise RuntimeError('internal APFS required')
 texts={};sources=[]
 for kind,(name,sha,url) in SOURCES.items():
  p=(root/FOLDER/name).resolve(strict=True)
  if root not in p.parents or p.is_symlink() or not 32<=p.stat().st_size<=12000000:raise ValueError('unsafe original')
  raw=p.read_bytes();receipt=json.loads(Path(str(p)+'.json').read_text())
  if hashlib.sha256(raw).hexdigest()!=sha or receipt['sha256']!=sha or receipt['source_url']!=url or receipt['case_id']!=CID or receipt['http_status']!=200 or receipt['relative_file']!=FOLDER+name:raise ValueError('source receipt drift')
  if kind=='technical':
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    if len(z.namelist())>200 or 'word/document.xml' not in z.namelist():raise ValueError('bad DOCX')
    xml=z.read('word/document.xml')
    if len(xml)>2000000:raise ValueError('oversized DOCX')
   texts[kind]=norm(' '.join(e.text or '' for e in ET.fromstring(xml).iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')))
  else:
   h=Text();h.feed(raw.decode('utf8','replace'));texts[kind]=norm(' '.join(h.parts))
  sources.append({'url':url,'sha256':sha,'source_tier':'first_party_eis_original'})
 if not all(x in texts['contract'] for x in ('50263017332260000870000','Номер договора: 304/26','Дата заключения договора: 21.09.2026','Цена договора: 3 865 725.99','32616296475')):raise ValueError('contract proof')
 if not all(x in texts['card'] for x in ('50263017332260000870000','Номер договора 304/26','Цена договора 3 865 725,99','21.09.2026','32616296475')):raise ValueError('registry proof')
 if not all(x in texts['protocol'] for x in ('Заявка №79410','Цена поставщика: 3 865 725.99','79410','1 место Да')):raise ValueError('commission proof')
 for pattern in (r'Номинальное напряжение сети:\s*не более 6,3\s*кВ',r'Номинальная реактивная мощность АУКРМ:\s*не менее 500\s*кВАр',r'тиристорные вентили',r'фильтр высших гармоник'):
  if not re.search(pattern,texts['technical'],re.IGNORECASE):raise ValueError('technical proof '+pattern)
 return sources


def validate(row):
 d=row['data']
 if (row['id']!=CID or row['owner']!='tender-agent' or d.get('canonical_id')!=CID
     or d.get('procedure_id')!='32616296475' or d.get('supplier_verified') is not False
     or d.get('pq_equipment_only_contract_rub') is not None or digest(d)!=row['hash']
     or any(d.get(k) is not None for k in FIELDS)
     or row['meta'].get('meleuz_eis_20261031_enrichment')):raise RuntimeError('identity/old-null CAS blocked')

def update(before,row,sources):
 validate(row)
 d={**row['data'],**FIELDS,
    'evidence':[*row['data']['evidence'],*[
     {**s,'excerpt':('Official signed registry, final commission, technical DOCX; no named supplier or equipment-only price')}
     for s in sources]]}
 h=digest(d)
 meta={**row['meta'],'source_content_hash':h,
       'meleuz_eis_20261031_enrichment':{
        'fields':FIELDS,'sources':sources,'previous_hash':row['hash'],
        'previous_revision':row['rev'],'supplier_verified':False,
        'equipment_only_price_verified':False,'payment_verified':False}}
 nulls=' AND '.join(f"(d.data->'{k}') IS NULL" for k in FIELDS)
 sql=f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
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
 AND d.revision={row['rev']} AND {nulls})<>1
THEN RAISE EXCEPTION 'PQ count/owner/CAS drift';END IF;END $g$;
UPDATE dp_records d SET data={js(d)},metadata={js(meta)},revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{row['hash']}' AND d.revision={row['rev']} AND {nulls};
UPDATE dp_resources SET content_hash='{h}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
 WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{h}'
 AND d.revision={row['rev']+1} AND d.data->>'contract_registered_price_rub'='3865725.99'
 AND d.metadata->'meleuz_eis_20261031_enrichment'->'sources'->0->>'sha256'='{SOURCES['contract'][1]}')<>1
THEN RAISE EXCEPTION 'PQ postwrite drift';END IF;END $g$;
COMMIT;"""
 psql(sql);after=snapshot();actual=get_row(CID)
 if before!=after or actual['hash']!=h or actual['rev']!=row['rev']+1 or any(actual['data'].get(k)!=v for k,v in FIELDS.items()):raise RuntimeError('postcommit readback mismatch')
 return {'before':before,'after':after,'new_verified_fields':len(FIELDS),'new_hash':h,'source_sha256':[x['sha256'] for x in sources]}

def main():
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true')
 p.add_argument('--backup-manifest',type=Path);p.add_argument('--receipt',type=Path);a=p.parse_args()
 sources=proof();before=snapshot();row=get_row(CID);validate(row)
 if not a.apply:
  print(json.dumps({'mode':'dry_run','before':before,'case':CID,'fields':FIELDS,'source_sha256':[x['sha256'] for x in sources]},ensure_ascii=False));return
 if not a.backup_manifest or not a.receipt:raise RuntimeError('fresh backup/receipt mandatory')
 gate=subprocess.run([sys.executable,'-m','scripts.market_intelligence.verify_internal_runtime'],capture_output=True,text=True,check=True,timeout=60)
 if json.loads(gate.stdout)['status']!='pass':raise RuntimeError('acceptance blocked')
 backup=verified_backup(a.backup_manifest)
 age=(datetime.now(UTC)-datetime.fromisoformat(backup['created_at_utc'])).total_seconds()
 if backup.get('pg_restore_list_verified') is not True or not 0<=age<=1800:raise RuntimeError('fresh verified full backup required')
 result=update(before,row,sources);result['backup_sha256']=backup['sha256']
 a.receipt.parent.mkdir(parents=True,exist_ok=True)
 with a.receipt.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()

