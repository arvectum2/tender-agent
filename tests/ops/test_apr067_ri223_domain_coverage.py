import copy

import pytest

from scripts.quality.apr067_ri223_domain_coverage import (
    COMPLETE,
    DOMAINS,
    case_measure,
    summarize,
)


def packet():
    domains=[{'domain':d,'citations':[{'original_sha256':'a'*64}] if i==0 else [],
              'status':'NEEDS_HUMAN_DOCUMENT_REVIEW' if i==0 else 'NO_CITED_DOCUMENT_EXCERPT',
              'requirements_verified':False} for i,d in enumerate(DOMAINS)]
    return {'status':'RI223_ARCHIVED_REVIEW_ONLY','inventory':{'archived_bytes_complete':True,
            'projection_complete':True,'originals_verified':1,'members_verified':0,'saved_searchable_candidates':1},
            'go_eligible':False,'requirements_verified':False,'current_revision_attested':False,
            'external_action_allowed':False,'decision':'NOT_DECIDED','domains':domains,'source_backed_domains':1}


def test_denominators_and_scope():
    rows=[case_measure(n,packet(),1.23) for n in COMPLETE]
    out=summarize(rows,True)
    assert out['probe_count']==45 and out['probes_with_citations']==5
    assert out['citation_occurrences']==5 and out['incomplete_cases_refused']==1
    assert out['semantic_precision'] is None and out['semantic_recall'] is None
    assert not out['rolling_slo'] and not out['commercial_acceptance']


@pytest.mark.parametrize('key',['go_eligible','requirements_verified','current_revision_attested','external_action_allowed'])
def test_refuse_promotion(key):
    data=packet();data[key]=True
    with pytest.raises(AssertionError):
        case_measure(COMPLETE[0],data,0.1)


def test_refuse_bad_denominator():
    rows=[case_measure(n,packet(),0.1) for n in COMPLETE]
    with pytest.raises(AssertionError):
        summarize(rows,False)
    with pytest.raises(AssertionError):
        summarize(rows[:-1],True)
    changed=copy.deepcopy(rows);changed[-1]['case']=rows[0]['case']
    with pytest.raises(AssertionError):
        summarize(changed,True)


def test_refuse_non_projected_inventory():
    data=packet();data['inventory']['projection_complete']=False
    with pytest.raises(AssertionError):
        case_measure(COMPLETE[0],data,0.1)
