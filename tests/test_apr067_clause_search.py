"""Development controls for contextual selection, not independent legal gold."""
import hashlib

import pytest
from test_apr08_document_search import RUN, TEXT
from test_apr08_document_search import archive as archive  # noqa: PLC0414

from src.modules.tender_operator_agent_demo import evidence_document_search as search
from src.modules.tender_operator_agent_demo.evidence_clause_search import (
    _saved_chunks,
    chunk_aligned_clause_candidate,
    clause_candidate,
)
from src.modules.tender_operator_agent_demo.evidence_document_search import _candidate

E={'критерий','оценки'}
C={'договор','ответственность','неустойка','расторжение'}


@pytest.mark.parametrize('terms,text',[
    (E,'Закон об оценочной деятельности. Кадастровая оценка имущества.'),
    (E,'Стороны согласовали стоимостную оценку неустойки.'),
    (E,'Критерии оценки имущества определяются приложением.'),
    (C,'Настоящее извещение о заключении договора с единственным поставщиком.'),
    (C,'В соответствии с условиями договора.'),
    (C,'Раздел 5. Ответственность сторон и расторжение договора.'),
])
def test_generic_mentions_not_clause_candidates(terms,text):
    assert clause_candidate(text,terms) is None


@pytest.mark.parametrize('terms,text',[
    (E,'3.2. Победителем признается участник, предложивший наименьшую цену договора.'),
    (E,'Критерии оценки заявок: цена и квалификация участника закупки.'),
    (C,'5.3. Подрядчик обязан уплачивать неустойку в размере 0,1% цены за каждый день просрочки.'),
    (C,'Заказчик вправе отказаться от исполнения договора при нарушении обязательств.'),
])
def test_complete_literal_clause(terms,text):
    result=clause_candidate(text,terms)
    assert result and result[1]==text


def test_rank_actual_quantified_terms_above_plain_clause():
    a='Подрядчик несет ответственность за ненадлежащее исполнение обязательств.'
    b='5.3. Подрядчик обязан уплачивать неустойку в размере 0,1% цены за каждый день просрочки.'
    assert clause_candidate(a+'\n'+b,C)[1]==b
    assert clause_candidate(a+'\n'+b,{'подрядчик'})==_candidate(a+'\n'+b,{'подрядчик'})


def test_full_line_bound_and_no_cross_line_synthesis():
    assert clause_candidate('Победитель определяется комиссией.\nНаименьшая цена.',E) is None
    assert clause_candidate('Подрядчик обязан уплачивать неустойку '+('условие '*200),C) is None

def _record(text,spans):
    normalized=" ".join(text.split())
    return {'file_id':'FILE-01','data_platform_source':{'offset_space':'data_platform_normalized_text',
      'resource_id':'r','document_id':'d','source_chunk_count':len(spans),'attributable_chunk_count':len(spans)},
      'evidence_chunks':[{'file_id':'FILE-01','resource_id':'r','document_id':'d','chunk_id':str(i),
                        'char_start':a,'char_end':b,'text_hash':hashlib.sha256(normalized[a:b].strip().encode()).hexdigest()}
                         for i,(a,b) in enumerate(spans)]}


def test_chunk_alignment_rejects_ambiguous_or_split_best_candidate():
    a='5.3. Подрядчик обязан уплачивать неустойку в размере 0,1% цены за каждый день просрочки.'
    b='Заказчик вправе отказаться от исполнения договора при нарушении обязательств.'
    text=a+'\n'+b
    record=_record(text,[(0,len(a)),(0,len(a)+1+len(b))])
    assert clause_candidate(text,C)[1]==a
    assert chunk_aligned_clause_candidate(text,C,record)[1]==b
    record=_record(text,[(0,40),(40,len(a)+1+len(b))])
    assert chunk_aligned_clause_candidate(text,C,record)[1]==b
    record['evidence_chunks'][0]['text_hash']='0'*64
    assert chunk_aligned_clause_candidate(text,C,record) is None


def test_normalized_whitespace_only():
    text='Подрядчик обязан  уплачивать неустойку за каждый день просрочки.'
    record=_record(text,[(0,len(" ".join(text.split())))])
    assert chunk_aligned_clause_candidate(text,C,record)[1]==' '.join(text.split())
    assert chunk_aligned_clause_candidate(text.replace('обязан','не обязан'),C,record) is None

def test_reconstructed_chunk_limits():
    text='a'*8193
    assert _saved_chunks(text,_record(text,[(0,len(text))])) is None
    text='a'*5000
    assert _saved_chunks(text,_record(text,[(0,len(text))]*6)) is None

def test_record_selector_still_requires_original_verifier(archive):
    run,_,calls=archive
    q=search.DocumentSearchQuestion(query='договор ответственность неустойка расторжение')
    out=search.search_run_documents(RUN,q,record_candidate_selector=chunk_aligned_clause_candidate)
    assert out['status']=='VERIFIED_EXCERPTS_ONLY'
    assert out['citations'][0]['quote']==TEXT and len(calls)==1
    assert not out['semantic_answer_verified'] and not out['bid_ready']
    (run/'input/original.docx').write_bytes(b'changed')
    out=search.search_run_documents(RUN,q,record_candidate_selector=chunk_aligned_clause_candidate)
    assert out['status']=='UNKNOWN' and not out['citations']
