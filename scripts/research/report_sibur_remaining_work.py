"""Read-only remaining workload by site, procedure and unique document URL."""
import argparse,collections,datetime,hashlib,json,os,subprocess
from pathlib import Path
from scripts.research.report_sibur_coverage import ALLOWED,QUERY,ext,load,sha
DIRECT={'ПАО "Нижнекамскнефтехим"':'Нижнекамскнефтехим','ООО "ЗапСибНефтехим"':'ЗапСибНефтехим','ПАО "Казаньоргсинтез"':'Казаньоргсинтез','ООО «ПОЛИОМ»':'ПОЛИОМ','ООО "НПП "Нефтехимия"':'НПП Нефтехимия','ООО "БИАКСПЛЕН"':'БИАКСПЛЕН','АО "СИБУР-Нефтехим"':'СИБУР-Нефтехим','ООО "АМУРСКИЙ ГХК"':'Амурский ГХК','ООО "СИБУР-Портэнерго"':'СИБУР-Портэнерго','АО "СибурТюменьГаз"':'СибурТюменьГаз','ООО "РусВинил"':'РусВинил','АО "Воронежсинтезкаучук"':'Воронежсинтезкаучук','ООО "Томскнефтехим"':'Томскнефтехим','АО "Сибур-Химпром"':'СИБУР-Химпром'}
def site(r):
    mentions=sorted(set(r['site_mentions']));direct=DIRECT.get(r['organizer'])
    if len(mentions)>1:return 'MULTI_SITE','multiple_explicit_mentions'
    if len(mentions)==1:
        if direct and direct!=mentions[0]:return 'UNRESOLVED_CONFLICT','organizer_site_conflict'
        return mentions[0],'explicit_site_mention'
    if direct:return direct,'organizer_affiliation_only'
    return 'UNRESOLVED','no_site_evidence'
def build(snap,projects,routing,sales,db,ev):
    byid={x['external_id']:x for x in snap};sales={x['external_id']:x for x in sales};ind={r['external_id'] for r in routing if 'industrial_equipment' in r['channels']};pm=collections.defaultdict(set);p0=set()
    for p in projects:
        for i in p['archive_publication_ids']:
            pm[i].add(p['project_id'])
            if p['priority_recommendation']=='P0':p0.add(i)
    union=set(pm);outside=ind-union;priority=ind|union;assert priority<=byid.keys() and outside<=sales.keys()
    committed={}
    for r in db:
        h=r['sha256'];i=r['external_id']
        for c in (r['raw_meta'] or {}).get('capture_receipts',[]):
            assert c['reference']['external_id']==i
            k=(i,c['url']);assert k not in committed or committed[k]==h;committed[k]=h
    pending={};groups=collections.defaultdict(lambda:dict(total=0,explicit=0,organizer_only=0,other=0,service=0,budget=0,all_known=0,any_extracted=0,without_urls=0,supported_urls=set(),extracted_supported=set(),families=collections.Counter()));rows=[];url_done=collections.defaultdict(set)
    def status(i,u):
        h=committed.get((i,u));return ev.get(h,'not_scanned') if h else 'not_committed'
    for i in sorted(priority):
        r=byid[i];urls={u for o in r['observations'] for u in o['documentation_urls']};sup={u for u in urls if ext(u) in ALLOWED};all_ex=bool(urls) and all(status(i,u)=='extracted' for u in urls) and not any(o.get('unverified_document_links') for o in r['observations']);any_ex=any(status(i,u)=='extracted' for u in urls)
        for u in sup:
            st=status(i,u)
            if st=='extracted':url_done[u].add(i);continue
            x=pending.setdefault(u,{'url':u,'format':ext(u),'p0':False,'projects':set(),'ids':set(),'pair_statuses':collections.Counter()});x['p0']|=i in p0;x['projects'].update(pm[i]);x['ids'].add(i);x['pair_statuses'][st]+=1
        if i not in outside:continue
        m=sales[i];name,basis=site(m);g=groups[name];g['total']+=1;g['explicit']+=basis=='explicit_site_mention';g['organizer_only']+=basis=='organizer_affiliation_only';g['other']+=basis not in ('explicit_site_mention','organizer_affiliation_only');g['service']+=bool(m['service_signal']);g['budget']+=bool(m['budget_signal']);g['all_known']+=all_ex;g['any_extracted']+=any_ex;g['without_urls']+=not urls;g['supported_urls'].update(sup);g['extracted_supported'].update(u for u in sup if status(i,u)=='extracted');g['families'].update(set(m['core_tags']));rows.append(dict(id=i,site_group=name,basis=basis,organizer=m['organizer'],site_mentions=m['site_mentions'],families=m['core_tags'],service=bool(m['service_signal']),budget=bool(m['budget_signal']),all_known_extracted=all_ex,any_extracted=any_ex,source_receipts=m['source_receipts']))
    queue=[]
    for u,x in pending.items():
        x['projects']=sorted(x['projects']);x['ids']=sorted(x['ids']);x['other_extracted_pairs']=len(url_done[u]);x['needs_acquisition']=bool(x['pair_statuses']['not_committed']) and sum(x['pair_statuses'].values())==x['pair_statuses']['not_committed'] and not url_done[u];queue.append(x)
    queue.sort(key=lambda x:(not x['p0'],not x['needs_acquisition'],not bool(x['projects']),x['format']=='.pdf',x['url']))
    for g in groups.values():
        for k in ('supported_urls','extracted_supported'):g[k]=len(g[k])
    summary={'priority_unique_publications':len(priority),'p0_unique_publications':len(p0),'outside_unique_publications':len(outside),'pending_pair_urls':len(queue),'pending_without_extracted_pair':sum(not x['other_extracted_pairs'] for x in queue),'p0_pending_urls':sum(x['p0'] for x in queue),'pending_formats':dict(collections.Counter(x['format'] for x in queue)),'pending_pair_statuses':dict(sum((x['pair_statuses'] for x in queue),collections.Counter())),'outside_basis':dict(collections.Counter(x['basis'] for x in rows))}
    return {'summary':summary,'site_groups':dict(sorted(groups.items(),key=lambda x:-x[1]['total'])),'outside_rows':rows,'pending_urls':queue,'note':'Organizer affiliation is not confirmed end buyer. Conflicting and multiple sites separate; no inferred project or award. Pending pair URLs may share extracted originals. No DB mutation.'}
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--map',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();os.umask(0o077);f=a.map.parent;inputs=[f/'db-observation-snapshot-v1.json',a.map,f/'sales-channel-routing-v1.json',f/'sales-map-v4.json'];snap,m,r,s=map(load,inputs);db=json.loads(subprocess.check_output(['docker','exec','arvectum-local-e2e-api-1','python','-c',QUERY],timeout=60));ev={}
    for p in (a.root/'technical-evidence/sibur').glob('*.evidence.json'):
        d=load(p);assert d['source_sha256']==p.name.removesuffix('.evidence.json');ev[d['source_sha256']]=d['status']
    out=build(snap,m['projects'],r['records'],s['candidates'],db,ev);out.update(schema='sibur_remaining_work_v1',observed_at=datetime.datetime.now(datetime.UTC).isoformat(),inputs={p.name:sha(p) for p in inputs});receipts=a.root/'sibur-archive-discovery/categories/documents'
    for row in out['pending_urls']:
        p=receipts/(hashlib.sha256(row['url'].encode()).hexdigest()+'.json');row['archive_receipt_status']=load(p)['status'] if p.exists() else 'unattempted';row['priority_acquisition_candidate']=row['needs_acquisition'] and row['archive_receipt_status']=='unattempted'
    out['summary']['p0_unattempted_candidate_urls']=sum(x['p0'] and x['priority_acquisition_candidate'] for x in out['pending_urls']);out['summary']['unattempted_candidate_urls']=sum(x['priority_acquisition_candidate'] for x in out['pending_urls']);out['summary']['pending_receipt_status']=dict(collections.Counter(x['archive_receipt_status'] for x in out['pending_urls']))
    with a.output.open('x') as o:json.dump(out,o,ensure_ascii=False,indent=2)
    print('SHA',sha(a.output),'SUMMARY',json.dumps(out['summary'],ensure_ascii=False));print('SITES name, total, explicit, affiliation, service, all_known, supported URL extracted/total')
    for k,x in out['site_groups'].items():print(k,x['total'],x['explicit'],x['organizer_only'],x['service'],x['all_known'],f"{x['extracted_supported']}/{x['supported_urls']}")
if __name__=='__main__':main()
