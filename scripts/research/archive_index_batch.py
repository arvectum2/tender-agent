"""Bounded archive queue adapter for the existing gated executor."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil
from pathlib import Path
from scripts.research.process_sibur_document_batch import operate, select_batch, require_prewrite, verified_bytes
from scripts.research.prepare_sibur_archive_index import FORMATS


def read(p): return json.loads(p.read_text())


def stage(root, digest):
    bridge=root/'sibur-sales-map-20261115/archive-index-bridge-v1.json'
    raw=bridge.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest: raise ValueError('bridge digest mismatch')
    b=json.loads(raw)
    if b['schema']!='sibur_archive_index_bridge_v1': raise ValueError('bridge schema')
    src=root/'sibur-archive-discovery/categories/documents'; dst=root/'documents'
    rows={}; priority=set()
    for r in b['ready']:
        sha=r['sha256']; p=src/r['file']; target=dst/p.name
        if p.parent!=src or p.is_symlink() or p.name!=sha+p.suffix or p.suffix not in FORMATS or sha in rows: raise ValueError('invalid source identity')
        buf=verified_bytes(p,sha)
        if len(buf)!=r['size_bytes']: raise ValueError('size mismatch')
        if target.exists():
            if target.is_symlink() or verified_bytes(target,sha)!=buf: raise ValueError('staged original mismatch')
        else:
            if shutil.disk_usage(dst).free<15*1024**3: raise ValueError('disk threshold')
            tmp=target.with_suffix(target.suffix+'.bridge-partial')
            with tmp.open('xb') as f: f.write(buf);f.flush();os.fsync(f.fileno())
            os.link(tmp,target);tmp.unlink()
        refs=[x['reference'] for x in r['committed_captures']]
        rows[sha]={'sha256':sha,'file':target.name,'bytes':len(buf),'references':refs}
        if r['p0_scope']:priority.update(x['external_id'] for x in refs)
    return rows,priority


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--digest',required=True);p.add_argument('--mode',choices=['extract','index']);p.add_argument('--gate',type=Path,required=True);p.add_argument('--limit',type=int,default=3);p.add_argument('--cap',type=int,default=100);a=p.parse_args();os.umask(0o077)
    require_prewrite(read(a.gate))
    if not 1<=a.limit<=5 or not 1<=a.cap<=100:raise ValueError('batch bounds')
    os.environ['TA_BATCH_REQUEST_TIMEOUT']='180'
    rows,priority=stage(a.root,a.digest);dst=a.root/'documents';batch=select_batch(dst,rows,priority,a.mode,a.limit,a.cap)
    for row in batch:
        result=operate(dst,row,a.mode);print(*result,flush=True)
        if result[1]=='review':raise SystemExit(2)
    print('planned',len(batch),flush=True)

if __name__=='__main__':main()
