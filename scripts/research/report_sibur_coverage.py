"""Read-only coverage by procedure, URL and original hash; never infer an award."""
import argparse,collections,datetime,hashlib,json,os,subprocess
from pathlib import Path
from urllib.parse import urlsplit
from scripts.research.acquire_sibur_documents import SUPPORTED
ALLOWED=SUPPORTED|{'.pptx'}
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ext(u):return Path(urlsplit(u).path).suffix.lower()
def calculate(snap,projects,routing,db,evidence):
    ids={r['external_id'] for r in snap};assert len(ids)==len(snap)
    urls={r['external_id']:{u for o in r['observations'] for u in o['documentation_urls']} for r in snap}
    unverified={r['external_id'] for r in snap if any(o.get('unverified_document_links',0) for o in r['observations'])}
    links=collections.defaultdict(dict); dbids=set();idxids=set(); idxhash=set(); originals=collections.defaultdict(set)
    for r in db:
        i,h=r['external_id'],r['sha256'];meta=r['raw_meta'] or {};dbids.add(i);dp=meta.get('dp_index');status=evidence.get(h,'not_scanned')
        if dp and dp.get('canonical_uri')=='content-sha256://'+h and dp.get('collection_id')=='tender-agent:sibur-public-research' and dp.get('extraction_status')=='extracted' and dp.get('chunks',0)>0 and dp.get('chunks')==dp.get('embeddings'):
            idxids.add(i);idxhash.add(h)
        for c in meta.get('capture_receipts',[]):
            if c['reference']['external_id']!=i:raise ValueError('mismatched ref')
            u=c['url'];prev=links[i].get(u)
            if prev and prev[0]!=h:raise ValueError('ambiguous URL identity')
            links[i][u]=(h,status);originals[h].add(i)
    def cohort(name,g):
        g=set(g);assert g<=ids;have_urls={i for i in g if urls[i]};sup={i:{u for u in urls[i] if ext(u) in ALLOWED} for i in g};eligible={i for i in g if sup[i]}
        full=lambda i,u:u in links[i] and links[i][u][1]=='extracted'
        captured={u for i in g for u in urls[i]&links[i].keys()}; allurls={u for i in g for u in urls[i]}; allsup={u for u in allurls if ext(u) in ALLOWED}; extracted={u for i in g for u in urls[i] if full(i,u)}; hashes={links[i][u][0] for i in g for u in urls[i]&links[i].keys()}
        complete={i for i in eligible if all(full(i,u) for u in sup[i])};allknown={i for i in have_urls if all(full(i,u) for u in urls[i])}
        return dict(name=name,total=len(g),with_urls=len(have_urls),eligible=len(eligible),db_linked=len(g&dbids),captured_any=sum(bool(urls[i]&links[i].keys()) for i in g),scanned_any=sum(any(v[1]!='not_scanned' for u,v in links[i].items() if u in urls[i]) for i in g),extracted_any=sum(any(full(i,u) for u in urls[i]) for i in g),narrow_any=sum(any(full(i,u) and len(originals[links[i][u][0]])<=5 for u in urls[i]) for i in g),all_supported_extracted=len(complete),all_known_extracted=len(allknown),all_known_no_unverified=len(allknown-unverified),indexed=len(g&idxids),urls=len(allurls),supported_urls=len(allsup),captured_supported_urls=len(allsup&captured),extracted_supported_urls=len(allsup&extracted),hashes=len(hashes),indexed_hashes=len(hashes&idxhash),unverified_markers=len(g&unverified))
    union={i for p in projects for i in p['archive_publication_ids']};industrial={r['external_id'] for r in routing if 'industrial_equipment' in r['channels']};assert industrial<=ids and union<=ids
    return {'cohorts':[cohort('all',ids),cohort('industrial',industrial),cohort('project_union',union),cohort('priority_union',industrial|union),cohort('industrial_in_projects',industrial&union),cohort('industrial_outside_projects',industrial-union),cohort('project_union_outside_industrial',union-industrial)],'projects':[{'id':p['project_id'],'priority':p['priority_recommendation'],**cohort(p['name'],p['archive_publication_ids'])} for p in projects],'memberships':sum(len(set(p['archive_publication_ids'])) for p in projects),'db':{'document_rows':len(db),'linked_procedures':len(dbids),'indexed_procedures':len(idxids),'indexed_originals':len(idxhash)},'index_hashes':sorted(idxhash)}
QUERY='''import json,os
from sqlalchemy import create_engine,text
with create_engine(os.environ['AI_CORP_DATABASE_URL']).connect() as c:
 c.execute(text('SET TRANSACTION READ ONLY'))
 q="select t.external_id,d.sha256,d.raw_meta from procurement_tender_documents d join procurement_tenders t on t.id=d.tender_id where t.source='sibur_public'"
 print(json.dumps([dict(x) for x in c.execute(text(q)).mappings()],ensure_ascii=False))
'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--map',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();os.umask(0o077);root=a.root;folder=a.map.parent;sf=folder/'db-observation-snapshot-v1.json';rf=folder/'sales-channel-routing-v1.json';bf=folder/'archive-index-bridge-v1.json';tf=root/'technical-evidence/sibur';df=root/'sibur-archive-discovery/categories/documents';now=datetime.datetime.now(datetime.UTC)
 db=json.loads(subprocess.check_output(['docker','exec','arvectum-local-e2e-api-1','python','-c',QUERY],timeout=60));ev={}
 for f in tf.glob('*.evidence.json'):
  d=load(f);h=f.name.removesuffix('.evidence.json');assert d['source_sha256']==h;ev[h]=d['status']
 receipts=[load(f) for f in df.glob('*.json') if len(f.stem)==64];result=calculate(load(sf),load(a.map)['projects'],load(rf)['records'],db,ev);br={x['sha256'] for x in load(bf)['ready']};result.update(schema='sibur_project_coverage_v1',observed_at=now.isoformat(),inputs={p.name:sha(p) for p in (sf,rf,bf,a.map)},technical_state=load(tf/'state.json'),archive_state=load(df/'state.json'),index_state=load(root/'autonomous-runner/state.json')['lanes']['sibur'],bridge_targets=len(br),bridge_indexed_linked=len(br&set(result.pop('index_hashes'))),archive_receipts={'attempted':len(receipts),'captured':sum(r['status']=='captured' for r in receipts),'review':sum(r['status']=='review' for r in receipts)})
 result['archive_hourly_samples']={str(h):sum(now-datetime.timedelta(hours=h)<=datetime.datetime.fromisoformat(r['observed_at'])<=now for r in receipts) for h in (1,3)}
 files=[(load(f)['source_sha256'],datetime.datetime.fromtimestamp(f.stat().st_mtime,datetime.UTC)) for f in (root/'documents').glob('persistent-pilot-*.json')];result['index_hourly_samples']={str(h):sum(s in br and now-datetime.timedelta(hours=h)<=t<=now for s,t in files) for h in (1,3)}
 result['note']='Frozen IDs and URL pairs matched to committed capture receipts and technical extraction status. All supported URLs extracted is not complete tender review; shared documents, unreadable and unsupported links, missing contracts and suppliers remain separate. Sequential live reads may vary.'
 with a.output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
 print('SHA',sha(a.output),'observed',result['observed_at']);print('COHORTS',json.dumps(result['cohorts'],ensure_ascii=False));print('PROJECTS: id, total, with_URL, eligible, any_extracted, all_supported_extracted, all_known_no_unverified, indexed, narrow_any')
 for x in result['projects']:print(x['id'],*[x[k] for k in ('total','with_urls','eligible','extracted_any','all_supported_extracted','all_known_no_unverified','indexed','narrow_any')])
 print('DB',result['db'],'receipts',result['archive_receipts'],'rates',result['archive_hourly_samples'],result['index_hourly_samples'],'bridge',result['bridge_indexed_linked'],result['bridge_targets'],'archive',result['archive_state']['supported_urls'],result['archive_state']['document_urls'])
if __name__=='__main__':main()
