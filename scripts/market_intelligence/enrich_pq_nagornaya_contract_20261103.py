"""Null-only EIS contract enrichment, Nagornaya 6 kV mixed EPC.

Registered contract != named signed supplier or paid equipment sales.
"""
import argparse
import hashlib
import json
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

CID = '223fz:32615614821:lot1'
NUM = '50277071467260002650000'
DIR = 'captures/223fz_32615614821_lot1/'
FILES = (
 ('20261102T233825710346Z-3ed2ba87-bf32935c6e5b4f99.bin', 'bf32935c6e5b4f99ef21f1f23a2532ae89a3ac4e889fdfac713e54701a5895c4', 'https://zakupki.gov.ru/epz/order/notice/protocol223/printForm/view.html?protocolGuid=69fa23e4-12ae-468a-8a72-545193165fc4&purchaseNoticeNumber=32615614821'),
 ('20261102T233825726847Z-7e07be0e-afea7b5c3a601a6f.bin', 'afea7b5c3a601a6f3c0c493e52f2a07e5245793769d71584f3131e4e21005e1c', 'https://zakupki.gov.ru/epz/order/notice/notice223/contract/printForm/viewXml.html?contractRegistrationNumber=50277071467260002650003'),
)
FIELDS = {'contract_registry_number':NUM,'contract_number':'РЭС-1.16.7/Д-01325','contract_signed_date':'2026-04-14','contract_registered_price_rub':'1833358.30','registered_signed_contract_verified':True,'protocol_offer_rub':'1833358.30'}

class Text(HTMLParser):
 def __init__(self): super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,t,a):
  if t in ('script','style'):self.skip+=1
 def handle_endtag(self,t):
  if t in ('script','style'):self.skip-=1
 def handle_data(self,s):
  if not self.skip and s.strip():self.parts.append(s.strip())

def proof():
 root=ROOT.resolve(strict=True)
 if root!=Path('/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live'):raise RuntimeError('internal APFS required')
 texts=[];sources=[]
 for name,sha,url in FILES:
  path=(root/DIR/name).resolve(strict=True)
  if root not in path.parents or path.is_symlink() or not 32<=path.stat().st_size<=1000000:raise ValueError('unsafe source')
  raw=path.read_bytes();m=json.loads(Path(str(path)+'.json').read_text())
  if hashlib.sha256(raw).hexdigest()!=sha or m['sha256']!=sha or m['source_url']!=url or m['relative_file']!=DIR+name or m['case_id']!=CID or m['http_status']!=200:raise ValueError('original SHA/receipt mismatch')
  t=Text();t.feed(raw.decode('utf8','replace'));texts.append(' '.join(' '.join(t.parts).replace('\xa0',' ').split()))
  sources.append({'url':url,'sha256':sha})
 if not all(x in texts[0] for x in ('32615614821-03','03.03.2026','Цена поставщика: 1 833 358.30','одна заявка','Заключение договора')):raise ValueError('official card quote missing')
 if not all(x in texts[1] for x in (NUM,'РЭС-1.16.7/Д-01325','14.04.2026','Цена договора: 1 833 358.30','32615614821','Лот № 1')):raise ValueError('official print quote missing')
 return {'sources':sources,'role':'registered_6kv_mixed_epc_not_equipment_sale','supplier_verified':False,'payment_verified':False,'nmck_is_not_signed_price':True}

def validate(row,evidence):
 d=row.get('data',{})
 if row.get('id')!=CID or row.get('owner')!='tender-agent' or d.get('canonical_id')!=CID or d.get('procedure_id')!='32615614821' or d.get('scope')!='epc' or d.get('reported_contract_total_rub')!='1833358.30' or d.get('contract_date')!='2026-04-14' or d.get('supplier_verified') is not False or d.get('pq_equipment_only_contract_rub') is not None or digest(d)!=row.get('hash') or any(d.get(k) is not None for k in FIELDS) or row.get('meta',{}).get('eis_nagornaya_contract_enrichment') or len(evidence['sources'])!=2:raise RuntimeError('CAS identity/old-null/source blocked')

def write(row,before,evidence):
 validate(row,evidence)
 data={**row['data'],**FIELDS}
 data['evidence']=[*row['data']['evidence'],*({'url':x['url'],'sha256':x['sha256'],'source_tier':'first_party_eis_registered_contract','excerpt':('Протокол 32615614821-03; одна заявка; предложение 1 833 358.30 ₽' if i==0 else 'Реестровый договор РЭС-1.16.7/Д-01325; 14.04.2026; 1 833 358.30 ₽')} for i,x in enumerate(evidence['sources']))]
 h=digest(data)
 meta={**row['meta'],'source_content_hash':h,'eis_nagornaya_contract_enrichment':{**evidence,'fields':FIELDS,'previous_hash':row['hash'],'previous_revision':row['rev']}}
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
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id) WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{row['hash']}' AND d.revision={row['rev']} AND {nulls})<>1
THEN RAISE EXCEPTION 'CAS owner/count/null mismatch';END IF;END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{row['hash']}' AND d.revision={row['rev']} AND {nulls};
UPDATE dp_resources SET content_hash='{h}',updated_at=now() WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id) WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{h}' AND d.revision={row['rev']+1} AND d.data->>'contract_registry_number'='{NUM}' AND d.data->>'contract_registered_price_rub'='1833358.30' AND d.data->>'registered_signed_contract_verified'='true' AND d.metadata->'eis_nagornaya_contract_enrichment'->'sources'->0->>'sha256'='{FILES[0][1]}')<>1 THEN RAISE EXCEPTION 'postwrite mismatch';END IF;END $g$;
COMMIT;"""
 psql(sql);after=snapshot();actual=get_row(CID)
 if before!=after or actual['hash']!=h or actual['rev']!=row['rev']+1 or any(actual['data'].get(k)!=v for k,v in FIELDS.items()):raise RuntimeError('postwrite readback mismatch')
 return {'case':CID,'before':before,'after':after,'fields':FIELDS,'new_verified_fields':len(FIELDS),'new_hash':h,'proof':evidence}

def main():
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--backup-manifest',type=Path);p.add_argument('--receipt',type=Path);a=p.parse_args()
 evidence=proof();before=snapshot();row=get_row(CID);validate(row,evidence)
 if not a.apply:
  print(json.dumps({'mode':'dry_run','case':CID,'before':before,'fields':FIELDS,'proof':evidence},ensure_ascii=False));return
 if not a.backup_manifest or not a.receipt:raise RuntimeError('backup/receipt mandatory')
 gate=subprocess.run([sys.executable,'-m','scripts.market_intelligence.verify_internal_runtime'],capture_output=True,text=True,check=True,timeout=60)
 if json.loads(gate.stdout)['status']!='pass':raise RuntimeError('preflight blocked')
 backup=verified_backup(a.backup_manifest)
 age=(datetime.now(UTC)-datetime.fromisoformat(backup['created_at_utc'])).total_seconds()
 if backup.get('pg_restore_list_verified') is not True or not 0<=age<=1800:raise RuntimeError('fresh full backup required')
 result=write(row,before,evidence);result['backup_sha256']=backup['sha256'];a.receipt.parent.mkdir(parents=True,exist_ok=True)
 with a.receipt.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
