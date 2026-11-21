"""Paired development trial, using the same source-attested archive cases."""
import json
import os
import time

from scripts.quality.apr067_ri223_domain_coverage import case_measure, summarize
from src.modules.tender_operator_agent_demo.evidence_clause_search import (
    chunk_aligned_clause_candidate,
    clause_candidate,
)
from src.modules.tender_operator_agent_demo.evidence_document_search import (
    checked_search_run,
)
from src.modules.tender_operator_agent_demo.ri223_offline_intake import import_archive
from src.modules.tender_operator_agent_demo.ri223_review_dossier import (
    build_archived_review,
)


def measure(runs,all_runs,root,incomplete_refused):
    n='32616445795'
    p=root/n
    ids={**all_runs,n:import_archive(runs,p/'ri223-soap.zip',n,
                      attachments=[p/'attachments/01-3727.rar'],expand_rar=True)}
    aligned=os.environ.get("APR067_CLAUSE_ALIGNED")=="1"
    options={"record_candidate_selector":chunk_aligned_clause_candidate} if aligned else {"candidate_selector":clause_candidate}
    old_rows=[]
    new_rows=[]
    changed=[]
    for n,run_id in sorted(ids.items()):
        run,meta=checked_search_run(run_id)
        t=time.monotonic()
        a=build_archived_review(run_id,run,meta)
        old_rows.append(case_measure(n,a,time.monotonic()-t))
        t=time.monotonic()
        b=build_archived_review(run_id,run,meta,**options)
        new_rows.append(case_measure(n,b,time.monotonic()-t))
        assert a['notice']==b['notice'] and a['inventory']==b['inventory']
        for x,y in zip(a['domains'],b['domains'],strict=True):
            if x['domain'] not in ('evaluation','contract'):
                assert x==y
                continue
            changed.append({'case':n,'domain':x['domain'],'before':x['citations'],'after':y['citations']})
        print('APR067_CLAUSE_CASE',n,old_rows[-1]['counts'],new_rows[-1]['counts'],flush=True)
    old=summarize(old_rows,incomplete_refused)
    new=summarize(new_rows,incomplete_refused)
    assert (old['probes_with_citations'],old['citation_occurrences'])==(29,42)
    print('APR067_CLAUSE_RANKING_PASS',json.dumps({'scope':'EXPLORATORY_SAME_CORPUS_NOT_GOLD','chunk_aligned':aligned,
      'baseline':old,'candidate':new,'targeted_domains':changed,'default_promoted':False,
      'semantic_precision':None,'semantic_recall':None},ensure_ascii=False),flush=True)
