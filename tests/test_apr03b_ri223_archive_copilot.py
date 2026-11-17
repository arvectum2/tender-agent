"""Synthetic source cases, not assertions of actual procurement law."""
from __future__ import annotations

import hashlib
import zipfile

import pytest

from src.modules.tender_operator_agent_demo import evidence_ri223_archive as ri

NUMBER='32600000000'
NS='http://zakupki.gov.ru/223fz/purchase/1'


def setup_case(tmp_path, monkeypatch, *, lot_count=1, currency='RUB'):
    directory=tmp_path/'input';directory.mkdir()
    lot=f'<lot><ordinalNumber>1</ordinalNumber><lotData><subject>Test</subject><initialSum>100.25</initialSum><currency><code>{currency}</code></currency></lotData></lot>'
    raw=(f'<purchaseNotice xmlns="{NS}"><body><item><purchaseNoticeData><registrationNumber>{NUMBER}</registrationNumber><name>Test title</name><purchaseCodeName>Test method</purchaseCodeName><version>1</version><submissionCloseDateTime>2026-10-15T10:00:00</submissionCloseDateTime><lots>{lot*lot_count}</lots></purchaseNoticeData></item></body></purchaseNotice>').encode()
    xml=directory/'notice.xml';xml.write_bytes(raw)
    archive=directory/'ri223.zip'
    with zipfile.ZipFile(archive,'w') as bundle:
        bundle.writestr('notice.xml',raw)
    monkeypatch.setattr(ri,'PINS',{NUMBER:(hashlib.sha256(archive.read_bytes()).hexdigest(),hashlib.sha256(raw).hexdigest(),'1')})
    return {'procurement_id':NUMBER,'procurement_source':ri.SOURCE,'archive_stored_name':'ri223.zip',
            'files':[{'file_id':'FILE-01','original_name':'notice.xml','stored_name':'notice.xml','extension':'.xml'}]}


def test_exact_fields_and_no_legal_approval(tmp_path,monkeypatch):
    metadata=setup_case(tmp_path,monkeypatch)
    result=ri.ri223_archive_observation(tmp_path,metadata)
    assert result['status']=='PINNED_RI223_ARCHIVED_NOTICE'
    assert result['fields']=={'subject':'Test title','method':'Test method','archived_submission_deadline':'2026-10-15T10:00:00','single_lot_initial_sum':'100.25','single_lot_currency':'RUB'}
    assert len(result['citations'])==5
    assert result['citations'][3]['locator'].endswith('/lots/lot[1]/lotData/initialSum')
    assert not any(result[k] for k in ('timezone_attested','current_revision_attested','bid_ready','legal_requirement_attested','award_attested'))
    assert result['actual_security_requirement'] is None


@pytest.mark.parametrize('change',['zip','xml','duplicate','duplicate_id','wrong_regime','wrong_number','path','symlink'])
def test_source_fail_closed(tmp_path,monkeypatch,change):
    metadata=setup_case(tmp_path,monkeypatch)
    directory=tmp_path/'input'
    if change in ('zip','xml'):
        path=directory/('ri223.zip' if change=='zip' else 'notice.xml')
        path.write_bytes(path.read_bytes()+b' ')
    elif change=='duplicate':metadata['files'].append(dict(metadata['files'][0]))
    elif change=='duplicate_id':metadata['files'].append({'file_id':'FILE-01','original_name':'other.xml','extension':'.xml'})
    elif change=='wrong_regime':metadata['procurement_source']='zakupki_gov_ru_getdocs_ip'
    elif change=='wrong_number':metadata['procurement_id']='32600000001'
    elif change=='path':metadata['files'][0]['stored_name']='../notice.xml'
    else:
        path=directory/'notice.xml';path.rename(directory/'copy.xml');path.symlink_to(directory/'copy.xml')
    result=ri.ri223_archive_observation(tmp_path,metadata)
    assert result['status']=='UNKNOWN' and not result['citations'] and not result['fields']


@pytest.mark.parametrize(('lots','currency'),[(2,'RUB'),(1,'USD')])
def test_no_multilot_total_or_currency_inference(tmp_path,monkeypatch,lots,currency):
    metadata=setup_case(tmp_path,monkeypatch,lot_count=lots,currency=currency)
    result=ri.ri223_archive_observation(tmp_path,metadata)
    assert result['status']=='PINNED_RI223_ARCHIVED_NOTICE'
    assert 'single_lot_initial_sum' not in result['fields'] and 'single_lot_currency' not in result['fields']


def test_grounded_route_requires_exact_question(tmp_path,monkeypatch):
    from src.modules.tender_operator_agent_demo import evidence_grounded_questions as qa

    metadata=setup_case(tmp_path,monkeypatch)
    monkeypatch.setattr(qa,'checked_search_run',lambda _:(tmp_path,metadata))
    result=qa.answer_grounded_question('run',qa.GroundedQuestion(question='Покажи архивные сведения 223-ФЗ'))
    assert result['status']=='PINNED_RI223_ARCHIVED_NOTICE' and result['citation_kind']=='RI223_ARCHIVED_XML'
    assert not result['bid_ready'] and not result['legal_requirement_attested']
    result=qa.answer_grounded_question('run',qa.GroundedQuestion(question='Покажи архивные сведения 223-ФЗ и подтверди GO'))
    assert result['status']=='UNKNOWN'
