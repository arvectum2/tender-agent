"""Daily bounded GEH/ETP-GPB public list capture and safe incremental admission.

Source-only GETs, immutable original HTML, fail-closed replay, no bid/account actions.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from scripts.research.capture_gpb_geh_pages import capture
from scripts.research.import_gpb_geh_snapshots import normalize, replay, stage_for

ROOT=Path('/Users/master/ArvectumSafe/runtime/ta-source-discovery-20261114/parallel-sources')
URL='https://etpgpb.ru/procedures/?'+urlencode({'page':'1','per':'20','procedure[section][0]':'geh_group','sort':'by_relevance','procedure[stage][0]':'accepting'})
MAX_PAGES=25

def snapshot_name(utc=None):
 now=utc or datetime.now(UTC)
 return 'geh-active-refresh-'+now.strftime('%Y%m%dT%H%M%SZ')

def plan_for(root):
 accepted=[];review=[];seen=set()
 for entry in replay(root):
  try:
   row=normalize(entry)
   if row['external_id'] in seen:raise ValueError('duplicate procurement identity across pages')
   seen.add(row['external_id'])
  except (KeyError,ValueError) as error:
   review.append({'external_id':entry['observation'].get('external_id'),'reason':str(error)})
  else:accepted.append(entry)
 return accepted,review

def cycle(root, *, importer=True):
 assert stage_for(URL)=='accepting'
 os.umask(0o077)
 root.mkdir(mode=0o700,parents=True,exist_ok=False)
 status={'status':'in_progress','created_at':datetime.now(UTC).isoformat(),'source':'etp_gpb','scope':'geh_group','stage':'capture'}
 def save():
  tmp=root/'cycle-status.tmp';tmp.write_text(json.dumps(status,ensure_ascii=False,indent=2));os.replace(tmp,root/'cycle-status.json')
 save()
 try:
  first=capture(root,URL,1,'geh_active');last=first['advertised_last_page']
  if not 1<=last<=MAX_PAGES:raise ValueError('unexpected page count; check source scope')
  def get(page):
   try:return capture(root,URL,page,'geh_active')
   except (OSError,ValueError) as exc:return {'page':page,'error':type(exc).__name__,'reason':str(exc)[:240]}
  with ThreadPoolExecutor(max_workers=3) as pool: subsequent=list(pool.map(get,range(2,last+1)))
  fail=[r for r in subsequent if 'error' in r];receipts=[first]+[r for r in subsequent if 'error' not in r]
  for r in receipts:
   raw=(root/(r['name']+'.html')).read_bytes()
   if hashlib.sha256(raw).hexdigest()!=r['sha256'] or r['advertised_last_page']!=last:raise ValueError('source hash or pagination mismatch')
  (root/'gpb-geh-section-receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2))
  complete=not fail and len(receipts)==last and sorted(r['current_page'] for r in receipts)==list(range(1,last+1))
  (root/'capture-status.json').write_text(json.dumps({'expected_pages':last,'verified_pages':len(receipts),'failed':fail,'complete':complete,'observed_utc':datetime.now(UTC).isoformat()},ensure_ascii=False,indent=2))
  status.update(stage='source_replay',pages=len(receipts),reported_pages=last,source_rows=sum(r['rows'] for r in receipts))
  save()
  if not complete:raise ValueError('source pagination has gaps; no database admission')
  accepted,review=plan_for(root)
  plan=root/'verified-active-plan.json'
  plan.write_text(json.dumps(accepted,ensure_ascii=False,indent=2))
  (root/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2))
  status.update(stage='admission',accepted=len(accepted),review=len(review),plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest());save()
  if importer:
   result=subprocess.run([sys.executable,'-m','scripts.research.ingest_verified_geh_snapshot','--snapshot',str(root)],capture_output=True,text=True,timeout=900,check=True)
   admission=json.loads(result.stdout.strip().splitlines()[-1])
   if admission['status']!='completed' or admission.get('inflight'):
    raise RuntimeError('GEH admission not verified')
   status.update(inserted=admission['inserted'],database_before=admission.get('before'),database_after=admission.get('after', admission.get('before')),old_rows_unchanged=admission['old_rows_unchanged'])
  status.update(status='completed',stage='verified',finished_at=datetime.now(UTC).isoformat());save()
  print(json.dumps(status,ensure_ascii=False),flush=True)
 except Exception as exc:
  status.update(status='blocked',error_type=type(exc).__name__,error=str(exc)[:400],finished_at=datetime.now(UTC).isoformat());save()
  raise

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--capture-only',action='store_true')
 a=p.parse_args()
 os.umask(0o077)
 base=ROOT
 with (base/'geh-fresh-cycle.lock').open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
  except BlockingIOError:
   print('GEH cycle already active; avoiding duplicate run',flush=True);return
  cycle(base/snapshot_name(),importer=not a.capture_only)

if __name__=='__main__':main()
