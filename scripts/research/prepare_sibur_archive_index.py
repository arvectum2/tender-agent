"""Read-only bridge from committed archive captures to the existing DP queue.

Only prepares hash-verified candidates. Does not stage files, ingest, or change DB.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
from collections import defaultdict, Counter
from pathlib import Path
from urllib.parse import urlsplit

from scripts.research.process_sibur_document_batch import verified_bytes
from scripts.research.reconciled_sibur_index import load as load_reconciled

SHA = re.compile(r'[0-9a-f]{64}')
FORMATS = {'.docx', '.xlsx', '.pptx'}
QUERY = '''import json,os
from sqlalchemy import create_engine,text
with create_engine(os.environ['AI_CORP_DATABASE_URL']).connect() as c:
 c.execute(text('SET TRANSACTION READ ONLY'))
 rows=c.execute(text("select t.external_id,d.sha256,d.raw_meta from procurement_tender_documents d join procurement_tenders t on t.id=d.tender_id where t.source='sibur_public'")).mappings()
 print(json.dumps([dict(r) for r in rows],ensure_ascii=False))
'''

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def key(url, ref):
    return (ref['external_id'], url, ref['source_sha256'], ref['source_row'])


def prepare(queue, source, db_rows, indexed):
    known = {}
    for r in db_rows:
        k = (r['external_id'], r['sha256'])
        if k in known:
            raise ValueError('duplicate DB identity')
        known[k] = r['raw_meta'] or {}
    receipts = defaultdict(list)
    for p in sorted(source.glob('*.json')):
        if not SHA.fullmatch(p.stem):
            continue
        r = json.loads(p.read_text())
        if r.get('status') != 'captured':
            continue
        if not SHA.fullmatch(r['sha256']):
            raise ValueError('invalid capture identity')
        if hashlib.sha256(r['url'].encode()).hexdigest() != p.stem:
            raise ValueError('invalid capture receipt filename')
        receipts[r['sha256']].append(r)
    ready, review = [], []
    seen = set()
    for row in queue['rows']:
        sha = row['sha256']
        if not SHA.fullmatch(sha) or sha in seen:
            raise ValueError('invalid or duplicate queue identity')
        seen.add(sha)
        if sha in indexed:
            review.append({'sha256':sha,'reason':'already_indexed'})
            continue
        p = source / row['file']
        if p.parent != source or p.is_symlink() or p.name != sha+p.suffix:
            raise ValueError('invalid original path')
        if p.suffix not in FORMATS:
            review.append({'sha256':sha,'reason':'format_review'})
            continue
        raw = verified_bytes(p,sha)
        if len(raw) != row['size_bytes']:
            raise ValueError('original size changed')
        commits = {}
        for r in receipts[sha]:
            u=urlsplit(r['url'])
            if u.scheme!='https' or u.netloc!='www.sibur.ru' or not u.path.startswith('/upload/tmp/example/') or u.query or u.fragment:
                raise ValueError('unexpected source')
            if r['file']!=p.name or r['bytes']!=len(raw):
                raise ValueError('capture/original mismatch')
            for ref in r['references']:
                meta=known.get((ref['external_id'],sha),{})
                item={k:r[k] for k in ('url','bytes','mime','file')}|{'reference':ref}
                if item in meta.get('capture_receipts',[]):
                    dp=meta.get('dp_index')
                    if dp is not None:
                        raise ValueError('unreconciled DB index receipt')
                    commits[key(r['url'],ref)]=item
        expected={(r['external_id'],r['source_url'],r['list_sha256'],r['source_row']) for r in row['source_refs']}
        if not expected or not expected<=commits.keys():
            review.append({'sha256':sha,'reason':'committed_receipt_missing','missing':len(expected-commits.keys())})
            continue
        ready.append({'sha256':sha,'file':p.name,'size_bytes':len(raw),'p0_scope':row['p0_scope'],'tags':row['tags'],'project_ids':row['project_ids'],'committed_captures':list(commits.values())})
    return {'schema':'sibur_archive_index_bridge_v1','status':'prepared_read_only','ready':ready,'review':review,'counts':{'ready':len(ready),'review':len(review),'ready_p0':sum(r['p0_scope'] for r in ready),'committed_links':sum(len(r['committed_captures']) for r in ready),'review_reasons':dict(Counter(r['reason'] for r in review))}}


def main():
    a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();os.umask(0o077)
    root=args.root; q=root/'sibur-sales-map-20261115/archive-index-readiness-v1.json';source=root/'sibur-archive-discovery/categories/documents';old=root/'documents'
    idx={json.loads(p.read_text())['source_sha256'] for p in old.glob('persistent-pilot-*.json')}|set(load_reconciled(old))
    rows=json.loads(subprocess.check_output(['docker','exec','arvectum-local-e2e-api-1','python','-c',QUERY],timeout=60))
    result=prepare(json.loads(q.read_text()),source,rows,idx);result.update(queue_sha256=digest(q),legacy_receipt_count=len(idx))
    with args.output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result['counts'],ensure_ascii=False),digest(args.output))

if __name__=='__main__':main()
