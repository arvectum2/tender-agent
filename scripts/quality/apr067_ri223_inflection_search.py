"""Compare opt-in discovery on the same archived receipt corpus; not holdout gold."""
import json
import os
import time

from scripts.quality.apr067_ri223_domain_coverage import case_measure, summarize
from src.modules.tender_operator_agent_demo.evidence_document_search import (
    checked_search_run,
)
from src.modules.tender_operator_agent_demo.evidence_inflection_search import (
    guarded_inflection_candidate,
    inflection_candidate,
)
from src.modules.tender_operator_agent_demo.ri223_offline_intake import import_archive
from src.modules.tender_operator_agent_demo.ri223_review_dossier import (
    build_archived_review,
)


def measure(runs,all_runs,root,incomplete_refused):
    number='32616445795'
    case=root/number
    ids={**all_runs,number:import_archive(runs,case/'ri223-soap.zip',number,
                           attachments=[case/'attachments/01-3727.rar'],expand_rar=True)}
    guarded = os.environ.get("APR067_INFLECTION_GUARDED")=="1"
    selector = guarded_inflection_candidate if guarded else inflection_candidate
    exact_rows=[]
    enhanced_rows=[]
    additions=[]
    for number,run_id in sorted(ids.items()):
        run,meta=checked_search_run(run_id)
        t=time.monotonic()
        a=build_archived_review(run_id,run,meta)
        exact_rows.append(case_measure(number,a,time.monotonic()-t))
        t=time.monotonic()
        b=build_archived_review(run_id,run,meta,candidate_selector=selector)
        enhanced_rows.append(case_measure(number,b,time.monotonic()-t))
        assert a['notice']==b['notice'] and a['inventory']==b['inventory']
        for old,new in zip(a['domains'],b['domains'],strict=True):
            # Exact hits always rank above inflection-only candidates.
            assert all(c in new['citations'] for c in old['citations']), (number,old['domain'])
            for c in new['citations']:
                if c not in old['citations']:
                    additions.append({'case':number,'domain':new['domain'],'new_domain':not old['citations'],
                                      'citation':c})
        print('APR067_INFLECTION_CASE',number,exact_rows[-1]['counts'],enhanced_rows[-1]['counts'],flush=True)
    old=summarize(exact_rows,incomplete_refused)
    new=summarize(enhanced_rows,incomplete_refused)
    assert (old['probes_with_citations'],old['citation_occurrences'])==(29,42)
    print('APR067_INFLECTION_REPLAY_PASS',json.dumps({'scope':'EXPLORATORY_SAME_CORPUS_NOT_GOLD','guarded_two_term':guarded,
          'baseline':old,'candidate':new,'added_citations':additions,'prior_citations_retained':True,
          'default_promoted':False,'semantic_precision':None,'semantic_recall':None},ensure_ascii=False),flush=True)
