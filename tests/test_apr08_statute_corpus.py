from dataclasses import replace
from hashlib import sha256

import pytest

from src.modules.tender_operator_agent_demo import evidence_statute_corpus as corpus


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    data = ('<html><body><h2>Федеральный закон от 5 апреля 2013 года № 44-ФЗ</h2>'
            '<p>(с изменениями на 14 июля 2022 года)</p><p>Статья 45. Тестовый заголовок</p>'
            '<p>Тестовый абзац, не являющийся законом.</p><p>Статья 46. Следующая статья</p>'
            '<p>Тестовый следующий абзац.</p></body></html>').encode()
    path = tmp_path/'44fz-rospatent.html'; path.write_bytes(data)
    item = replace(corpus.SNAPSHOTS[0], sha256=sha256(data).hexdigest())
    monkeypatch.setattr(corpus, 'SNAPSHOTS', (item,))
    monkeypatch.setenv('AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR', str(tmp_path))
    return path, item


def lookup(**kwargs):
    return corpus.lookup_statute_snapshot(**{'act':'44-ФЗ','article':'45','requested_date':'2022-07-14','mode':'explicit_snapshot', **kwargs})


def test_pinned_historical_excerpt_not_current_law(snapshot):
    result = lookup()
    assert result['status'] == 'HISTORICAL_STATUTE_SNAPSHOT_EXCERPT'
    assert result['snapshot_bytes_verified'] is True
    assert result['statute_text_verified'] is False and result['current_law_verified'] is False
    assert result['reviewed_effective_interval'] is None and result['legal_conclusion'] is None
    assert not result['article_complete'] and not result['applicability_verified']
    cite = result['citations'][0]
    assert cite['excerpt'] == 'Статья 45. Тестовый заголовок\nТестовый абзац, не являющийся законом.'
    assert cite['source_sha256'] == snapshot[1].sha256
    assert cite['locator'].startswith('HTML p[2..3]')


@pytest.mark.parametrize('kwargs,reason', [({'mode':'as_of'},'NO_REVIEWED_EFFECTIVE_INTERVAL'),({'requested_date':'2026-11-17'},'SNAPSHOT_NOT_UNIQUE_OR_MISSING'),({'requested_date':'2022-02-31'},'INVALID_DATE'),({'act':'223-ФЗ'},'SNAPSHOT_NOT_UNIQUE_OR_MISSING'),({'article':'46'},'ARTICLE_END_NOT_BOUNDED'),({'article':'999'},'ARTICLE_NOT_UNIQUE_OR_MISSING')])
def test_no_implicit_replacement(snapshot, kwargs, reason):
    result = lookup(**kwargs)
    assert result['status'] == 'UNKNOWN' and result['reason'] == reason and result['citations'] == []


def test_tamper_and_duplicate_catalog_fail_closed(snapshot, monkeypatch):
    path, item = snapshot
    path.write_bytes(path.read_bytes()+b' ')
    assert lookup()['reason'] == 'SNAPSHOT_HASH_MISMATCH'
    monkeypatch.setattr(corpus, 'SNAPSHOTS', (item,item))
    assert lookup()['reason'] == 'SNAPSHOT_NOT_UNIQUE_OR_MISSING'


def test_missing_configuration_and_symlink(snapshot, monkeypatch, tmp_path):
    path, _ = snapshot
    monkeypatch.delenv('AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR')
    assert lookup()['reason'] == 'SNAPSHOT_STORAGE_NOT_CONFIGURED'
    monkeypatch.setenv('AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR',str(tmp_path))
    target = tmp_path/'copy.html'; path.rename(target); path.symlink_to(target)
    assert lookup()['reason'] == 'SNAPSHOT_FILE_UNSAFE_OR_MISSING'


def test_question_explicit_snapshot_and_as_of(snapshot, monkeypatch):
    from src.modules.tender_operator_agent_demo import evidence_grounded_questions as qa
    monkeypatch.setattr(qa, 'checked_search_run', lambda _id: (None, {}))
    result = qa.answer_grounded_question('test',qa.GroundedQuestion(question='Покажи статью 45 44-ФЗ из снимка 14.07.2022'))
    assert result['status'] == 'HISTORICAL_STATUTE_SNAPSHOT_EXCERPT' and result['citation_kind'] == 'GOVERNMENT_REPRODUCTION'
    assert not result['bid_ready'] and not result['legal_requirement_attested']
    result = qa.answer_grounded_question('test',qa.GroundedQuestion(question='Покажи статью 45 44-ФЗ на дату 14.07.2022'))
    assert result['status'] == 'UNKNOWN' and not result['citations']
