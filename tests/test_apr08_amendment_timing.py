from hashlib import sha256

import pytest

from src.modules.tender_operator_agent_demo import evidence_amendment_timing as timing


@pytest.fixture
def pinned(tmp_path, monkeypatch):
    # Synthetic fixtures exercise integrity and temporal behavior, not real law.
    lines = ['1. synthetic general', '2. synthetic publication', '3. synthetic later']
    pub = 'synthetic publication record'
    sources = []
    for i, texts in enumerate((lines, lines, [pub])):
        raw = ('<html><body>'+''.join('<p>'+s+'</p>' for s in texts)+'</body></html>').encode()
        filename = f'fixture{i}.html'
        (tmp_path/filename).write_bytes(raw)
        sources.append((filename,sha256(raw).hexdigest(),f'https://example.invalid/{i}',tuple(range(1,len(texts)+1))))
    monkeypatch.setattr(timing,'SOURCES',tuple(sources))
    monkeypatch.setattr(timing,'CLAUSE_HASHES',tuple(sha256(s.encode()).hexdigest() for s in lines))
    monkeypatch.setattr(timing,'PUBLICATION_LITERAL',pub)
    monkeypatch.setenv('AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR',str(tmp_path))
    return tmp_path


@pytest.mark.parametrize(('day','reached'), [('2026-08-03',[]),('2026-08-04',[2]),('2026-09-30',[2]),('2026-10-01',[1,2]),('2026-12-31',[1,2]),('2027-01-01',[1,2,3])])
def test_calendar_boundaries_not_legal_effect(pinned,day,reached):
    result=timing.amendment_timing(day)
    assert result['status']=='SECONDARY_AMENDMENT_TIMING_ONLY'
    assert [g['article2_part'] for g in result['groups'] if g['calendar_relation']=='DATE_REACHED']==reached
    assert all(not g['effective_status_verified'] for g in result['groups'])
    assert not result['official_publication_verified'] and not result['consolidated_edition_verified'] and result['legal_conclusion'] is None
    assert result['groups'][1]['date_basis']=='SECONDARY_REPORTED_PUBLICATION_DATE'
    assert len(result['citations'])==3


def test_corrupt_or_conflicting_sources(pinned,monkeypatch):
    path=pinned/'fixture1.html';path.write_bytes(path.read_bytes()+b' ')
    assert timing.amendment_timing('2026-11-17')['reason']=='AMENDMENT_EVIDENCE_UNAVAILABLE'
    raw=path.read_bytes().replace(b'synthetic general',b'conflicting text');path.write_bytes(raw)
    sources=list(timing.SOURCES);s=sources[1];sources[1]=(s[0],sha256(raw).hexdigest(),s[2],s[3]);monkeypatch.setattr(timing,'SOURCES',tuple(sources))
    assert timing.amendment_timing('2026-11-17')['reason']=='AMENDMENT_EVIDENCE_CONFLICT'


def test_invalid_or_missing_source(pinned,monkeypatch):
    assert timing.amendment_timing('2026-02-30')['reason']=='INVALID_DATE'
    monkeypatch.delenv('AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR')
    assert timing.amendment_timing('2026-11-17')['status']=='UNKNOWN'


def test_natural_question_nonbinding(pinned,monkeypatch):
    from src.modules.tender_operator_agent_demo import evidence_grounded_questions as qa
    monkeypatch.setattr(qa,'checked_search_run',lambda _:(None,{}))
    result=qa.answer_grounded_question('test',qa.GroundedQuestion(question='Покажи сроки вступления в силу 279-ФЗ на дату 17.11.2026'))
    assert result['status']=='SECONDARY_AMENDMENT_TIMING_ONLY' and not result['legal_requirement_attested'] and not result['bid_ready']
