"""Candidate discovery tests, not a semantic/qualification gold dataset."""
import pytest
from test_apr08_document_search import RUN, TEXT
from test_apr08_document_search import archive as archive  # noqa: PLC0414

from src.modules.tender_operator_agent_demo import evidence_document_search as search
from src.modules.tender_operator_agent_demo.evidence_inflection_search import (
    guarded_inflection_candidate,
    inflection_candidate,
)


@pytest.mark.parametrize('term,text',[
    ('оплаты','Оплата производится после подписания акта.'),
    ('критерий','Сопоставление проводится согласно критериям документации.'),
    ('объем','Объём услуг определяется приложением к договору.'),
    ('объём','Объем услуг определяется приложением к договору.'),
])
def test_literal_inflection_candidate(term,text):
    out=inflection_candidate(text,{term})
    assert out and out[0]>0 and out[1] in text and search._candidate(text,{term}) is None


@pytest.mark.parametrize('term,text',[
    ('автоматизация','Документация автоматизированной системы управления.'),
    ('суд','Сударь прочитал условия договора поставки.'),
    ('кредит','Аккредитация поставщика проводится ежегодно.'),
    ('ABC','Оборудование согласно маркировке ABCD.'),
])
def test_no_prefix_or_derivation(term,text):
    assert inflection_candidate(text,{term.casefold()}) is None


def test_exact_first():
    text='Согласно критериям документации выбираются условия.\nКритерий оценки определяется заказчиком.'
    baseline=search._candidate(text,{'критерий','оценки'})
    result=inflection_candidate(text,{'критерий','оценки'})
    assert result[1]==baseline[1] and result[0]>16


def test_opt_in_literal_and_tamper(archive):
    run,_,calls=archive
    q=search.DocumentSearchQuestion(query='оплаты')
    assert search.search_run_documents(RUN,q)['status']=='UNKNOWN'
    result=search.search_run_documents(RUN,q,candidate_selector=inflection_candidate)
    assert result['status']=='VERIFIED_EXCERPTS_ONLY' and result['citations'][0]['quote']==TEXT
    assert result['verification_attempts']==1 and len(calls)==1
    assert not result['bid_ready'] and not result['semantic_answer_verified']
    (run/'input/original.docx').write_bytes(b'modified')
    result=search.search_run_documents(RUN,q,candidate_selector=inflection_candidate)
    assert result['status']=='UNKNOWN' and not result['citations']

def test_guarded_multi_term_needs_two_distinct_keys():
    terms={'критерий','оценки'}
    # No exact term in this distinct synthetic false-positive example.
    irrelevant='В книге указаны подходы к оценке имущества.'
    assert inflection_candidate(irrelevant,terms)
    assert guarded_inflection_candidate(irrelevant,terms) is None
    correct='Результаты сопоставляются по критериям оценкой заявок.'
    assert guarded_inflection_candidate(correct,terms)
    assert guarded_inflection_candidate('Оплата производится по акту.',{'оплаты'})
    repeated='Оценка и оценке посвящены отдельные положения.'
    assert guarded_inflection_candidate(repeated,{'оценки','оценку'}) is None
