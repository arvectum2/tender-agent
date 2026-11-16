from datetime import UTC, datetime

import pytest

from src.modules.saas_foundation.commercial_card_evidence import verify_card_snapshot

WORKSPACE = 'https://workspace.ru/tenders/fixture-site-development-19043/'
B2B = 'https://www.b2b-center.ru/app/market-next/fixture-site-development/tender-4643484/'
NOW = datetime(2026, 10, 17, 12, tzinfo=UTC)


def workspace(stage='Идет прием заявок', deadline='31 октября 2026', organizer='Юридическое лицо', visibility='_public', canonical=WORKSPACE):
    return f'''<html><head><link rel="canonical" href="{canonical}"></head><body>
    <h1>Разработка корпоративного сайта</h1><div class="tendercart-type__status-public">{stage}</div>
    <span class="reference {visibility}">Публичный тендер</span>
    <section>Oрганизатор<div>{organizer}</div></section>
    <section>Крайний срок приема заявок:<div>{deadline}</div></section></body></html>'''.encode()


def b2b(stage='Приём заявок', deadline='до 21.10.2026 06:00, по МСК', heading='Разработка сайта № 4643484'):
    return f'''<html><body><h1>{heading}</h1><div>{stage}</div><div>{deadline}</div><section>Организатор:<strong>АО ФИКСТУРА</strong></section></body></html>'''.encode()


def verify(raw, url=WORKSPACE, **overrides):
    values = {'requested_url': url, 'final_url': url, 'raw': raw, 'observed_at': NOW, 'status_code': 200, 'tls_verified': True, 'content_type': 'text/html; charset=utf-8'}
    values.update(overrides)
    return verify_card_snapshot(**values)


def test_workspace_observation_is_not_bid_authorization():
    import hashlib

    raw = workspace()
    result = verify(raw)
    assert result['external_id'] == '19043'
    assert result['html_sha256'] == hashlib.sha256(raw).hexdigest()
    assert result['observation_state'] == 'PUBLIC_STAGE_AT_CAPTURE_ONLY'
    assert result['displayed_deadline'] == '2026-10-31'
    assert result['deadline_precision'] == 'date_only'
    assert result['organizer_type'] == 'Юридическое лицо'
    for field in ('external_submission_allowed', 'current_live_notice_status_verified', 'qualification_verified', 'full_documents_verified', 'legal_identity_verified'):
        assert result[field] is False


@pytest.mark.parametrize(('changes', 'state'), [
    ({'stage': 'Завершён'}, 'CLOSED_AT_CAPTURE'),
    ({'deadline': '16 октября 2026'}, 'CLOSED_AT_CAPTURE'),
    ({'deadline': '17 октября 2026'}, 'CUTOFF_TIME_UNKNOWN'),
    ({'organizer': 'Частное лицо'}, 'PERSONAL_ORGANIZER_REVIEW'),
])
def test_workspace_stage_and_deadline(changes, state):
    assert verify(workspace(**changes))['observation_state'] == state


@pytest.mark.parametrize('changes', [
    {'visibility': '_private'}, {'canonical': WORKSPACE.replace('19043', '19044')},
    {'stage': 'Неизвестно'}, {'deadline': '31 февраля 2026'}, {'organizer': 'Не указан'},
])
def test_workspace_unverified_body_rejected(changes):
    with pytest.raises(ValueError):
        verify(workspace(**changes))


@pytest.mark.parametrize('overrides', [
    {'status_code': 403}, {'status_code': 404}, {'tls_verified': False},
    {'final_url': 'https://workspace.ru/tenders/'}, {'content_type': 'application/json'},
    {'observed_at': datetime(2026, 10, 17)},
])
def test_transport_errors_never_become_card_observations(overrides):
    with pytest.raises(ValueError):
        verify(workspace(), **overrides)


def test_conflicting_duplicate_status_and_missing_canonical_rejected():
    with pytest.raises(ValueError):
        verify(workspace().replace(b'</body>', b'<div class="tendercart-type__status-public">Other</div></body>'))
    with pytest.raises(ValueError):
        verify(workspace().replace(b'rel="canonical"', b'rel="alternate"'))


def test_hidden_content_does_not_override_displayed_card():
    raw = workspace().replace(b'</body>', b'<div hidden class="tendercart-type__status-public">Other</div><script>Another procurement</script></body>')
    assert verify(raw)['observation_state'] == 'PUBLIC_STAGE_AT_CAPTURE_ONLY'


def test_b2b_exact_number_deadline_and_literal_organizer():
    result = verify(b2b(), B2B)
    assert result['external_id'] == '4643484'
    assert result['displayed_deadline'] == '2026-10-21T06:00:00+03:00'
    assert result['organizer_name_literal'] == 'АО ФИКСТУРА'
    assert result['organizer_type'] is None and not result['legal_identity_verified']
    assert result['observation_state'] == 'PUBLIC_STAGE_AT_CAPTURE_ONLY'
    assert verify(b2b(stage='Завершён'), B2B)['observation_state'] == 'CLOSED_AT_CAPTURE'
    assert verify(b2b(), B2B, observed_at=datetime(2026, 10, 21, 3, tzinfo=UTC))['observation_state'] == 'CLOSED_AT_CAPTURE'


@pytest.mark.parametrize('raw', [b2b(heading='Другая закупка 4643485'), b2b(heading='Другая закупка 14643484'), b2b(deadline='до 21.10.2026 06:00'), b2b().replace(b'</body>', '<div>Приём заявок</div></body>'.encode())])
def test_ambiguous_or_mismatched_b2b_card_rejected(raw):
    with pytest.raises(ValueError):
        verify(raw, B2B)
