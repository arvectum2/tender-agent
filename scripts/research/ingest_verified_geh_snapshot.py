"""Idempotently admit only new first-party GEH observations with source-scoped locking.

Read-only on old records. Never retry an unconfirmed prior write automatically.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path('/Users/master/ArvectumSafe/runtime/ta-source-discovery-20261114')
RUN = ROOT / 'autonomous-runner'
GPB = Path('/Users/master/ArvectumSafe/worktrees/ta-gpb-discovery-20261114')
MI = Path('/Users/master/ArvectumSafe/worktrees/tender-agent-mi')
VENV_PY = '/Users/master/ArvectumSafe/.venvs/tender-agent-mi/bin/python'
API = 'arvectum-local-e2e-api-1'
DB_CODE = '''import json,os
from sqlalchemy import create_engine,text
with create_engine(os.environ['AI_CORP_DATABASE_URL']).connect() as c:
 assert c.execute(text('select current_database()')).scalar_one()=='arvectum_local'
 rows=c.execute(text("select external_id,content_hash from procurement_tenders where source='etp_gpb'")).all()
 print(json.dumps([list(r) for r in rows],ensure_ascii=False))
'''

def utc(): return dt.datetime.now(dt.UTC).isoformat()
def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def atomic(path,obj):
 tmp=path.with_name(path.name+'.tmp')
 with tmp.open('x') as f:
  json.dump(obj,f,ensure_ascii=False,indent=2)
  f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
def cmd(args,*,cwd=None,timeout=180,input=None):
 p=subprocess.run(args,cwd=cwd,input=input,capture_output=True,timeout=timeout,check=False)
 if p.returncode:
  raise RuntimeError(f'{args[0]} failed rc={p.returncode} stderr_tail={p.stderr[-550:].decode(errors="replace")}')
 return p.stdout
def ids():return dict(json.loads(cmd(['docker','exec',API,'python','-c',DB_CODE],timeout=50)))
def locks():
 src=Path('/Users/master/ArvectumSafe/worktrees/ta-source-concurrency-20261120/scripts/research/source_write_locks.py')
 spec=importlib.util.spec_from_file_location('existing_source_write_locks',src)
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 return mod

def process(snapshot):
 from scripts.research.import_gpb_geh_snapshots import normalize, replay
 from scripts.research.run_gpb_archive_import import backup_ta
 os.umask(0o077)
 parent=ROOT/'parallel-sources'
 if not re.fullmatch(r'geh-active-refresh-\d{8}T\d{6}Z',snapshot.name) or snapshot.is_symlink() or snapshot.resolve().parent!=parent.resolve():
  raise ValueError('snapshot is outside verified GEH capture root')
 summary=json.loads((snapshot/'capture-status.json').read_text())
 receipts=json.loads((snapshot/'gpb-geh-section-receipts.json').read_text())
 n=summary['expected_pages']
 if not summary['complete'] or summary['verified_pages']!=n or len(receipts)!=n or sorted(r['current_page'] for r in receipts)!=list(range(1,n+1)) or any(r['advertised_last_page']!=n for r in receipts):
  raise ValueError('source pagination incomplete or drifted')
 accepted=[];reviews=[];seen=set()
 for entry in replay(snapshot):
  try:
   row=normalize(entry)
   if row['external_id'] in seen:raise ValueError('duplicate source identity')
   seen.add(row['external_id'])
  except (KeyError,ValueError) as exc:reviews.append((entry['observation']['external_id'],str(exc)))
  else:accepted.append(entry)
 plan=snapshot/'verified-active-plan.json'
 if sha(plan)!=hashlib.sha256(json.dumps(accepted,ensure_ascii=False,indent=2).encode()).hexdigest() or accepted!=json.loads(plan.read_text()):
  raise ValueError('source replay plan changed')
 status_dir=snapshot/'guarded-ingest';status_dir.mkdir(mode=0o700,exist_ok=True)
 state_file=status_dir/'state.json'
 if state_file.exists():
  prior_state=json.loads(state_file.read_text())
  if prior_state['status']=='completed':print(json.dumps(prior_state,ensure_ascii=False));return
  raise RuntimeError('unconfirmed previous attempt; manual reconciliation required')
 state={'status':'in_progress','created_at':utc(),'snapshot':str(snapshot),'plan_sha256':sha(plan),'valid':len(accepted),'review':len(reviews),'stage':'preflight'}
 def save(**kw):state.update(kw,updated_at=utc());atomic(state_file,state)
 save()
 lock=locks()
 try:
  # Same source-scoped locks as the running SIBUR/GEH workers, no concurrent GPB writer.
  with lock.source_guard(RUN,'gpb',lambda:(RUN/'STOP').exists()):
   if shutil.disk_usage(ROOT).free < 15*1024**3:raise RuntimeError('disk safety threshold')
   existing=ids();new=[e for e in accepted if e['observation']['external_id'] not in existing]
   changed_known=sum(normalize(e)['content_hash']!=existing[e['observation']['external_id']] for e in accepted if e['observation']['external_id'] in existing)
   save(stage='reconciled',before=len(existing),new=len(new),known_changed_immutable=changed_known)
   if not new:
    save(status='completed',stage='no_new',inserted=0,replay_inserted=0,old_rows_unchanged=True)
    print(json.dumps(state,ensure_ascii=False));return
   # A shared backup gate serializes MI snapshots across independent source workers.
   with lock.backup_guard(RUN,lambda:False):
    save(stage='fresh_MI_backup')
    backup=json.loads(cmd([VENV_PY,'-m','scripts.market_intelligence.backup_pq_postgres'],cwd=MI,timeout=330))
    gate=json.loads(cmd([VENV_PY,'-m','scripts.market_intelligence.verify_internal_runtime'],cwd=MI,timeout=150))
    if gate.get('status')!='pass' or gate.get('postgresql_mutated_by_preflight') is not False or backup.get('sha256')!=gate.get('backup',{}).get('sha256'):
     raise RuntimeError('MI acceptance gate or backup identity failed')
    receipt=backup_ta(status_dir)
    save(stage='backups_verified',mi_sha=backup['sha256'],ta_backup=receipt)
   raw=json.dumps({'accepted':new},ensure_ascii=False).encode()
   payload=status_dir/'new-only.json'
   with payload.open('xb') as out:
    out.write(raw);out.flush();os.fsync(out.fileno())
   save(stage='inflight',inflight=True,source_input_sha256=sha(payload))
   importer=(GPB/'scripts/research/import_gpb_geh_snapshots.py').read_text()
   result=json.loads(cmd(['docker','exec','-i',API,'python','-c',importer],cwd=GPB,timeout=180,input=raw))
   replayed=json.loads(cmd(['docker','exec','-i',API,'python','-c',importer],cwd=GPB,timeout=180,input=raw))
   after=ids()
   if result['inserted']!=len(new) or replayed['inserted'] or replayed['verified']!=len(new) or len(after)!=len(existing)+len(new) or any(after.get(k)!=v for k,v in existing.items()):
    raise RuntimeError('post-import source identity, replay or immutable history failed')
   if any(after.get(normalize(v)['external_id'])!=normalize(v)['content_hash'] for v in new):
    raise RuntimeError('new source hashes mismatch')
   save(status='completed',stage='verified',inflight=False,inserted=result['inserted'],after=len(after),result=result,replay_inserted=0,old_rows_unchanged=True)
   print(json.dumps(state,ensure_ascii=False))
 except Exception as exc:
  save(status='blocked',error_type=type(exc).__name__,error=str(exc)[:500])
  raise

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--snapshot',type=Path,required=True)
 args=parser.parse_args()
 process(args.snapshot)
if __name__=='__main__':main()
