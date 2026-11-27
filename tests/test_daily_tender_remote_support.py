from datetime import UTC, datetime

import pytest

from src.modules.daily_tender_run.profiles import load_daily_tender_profile
from src.modules.daily_tender_run.service import _screen_card


@pytest.mark.parametrize(('title', 'expected'), [
    ('Оказание услуг по техническому обслуживанию официального сайта администрации сельского поселения Нижнесортымский', 'IN'),
    ('Оказание услуг по поддержке и обслуживанию сайта в сети Интернет', 'IN'),
    ('Сопровождение сайта учреждения', 'IN'),
    ('Сопровождение систем информационного обеспечения деятельности: Консультант плюс', 'OUT'),
    ('Поставка оборудования и техническая поддержка сайта', 'OUT'),
    ('Предоставление неисключительных прав и сопровождение сайта', 'OUT'),
    ('Аттестации информационной системы и сопровождение сайта', 'OUT'),
])
def test_reference_building_support_screen(title, expected):
    profile = load_daily_tender_profile('arvectum-it')
    result, _, reasons = _screen_card(profile, {
        'title': title, 'initial_price': 12000, 'deadline': '31.12.2026 18:00',
    }, now=datetime(2026, 11, 27, tzinfo=UTC))
    assert result == expected
    if expected == 'IN':
        assert 'remote_support_candidate_requires_scope_review' in reasons


def test_support_does_not_override_expiry():
    profile = load_daily_tender_profile('arvectum-it')
    result, _, reasons = _screen_card(profile, {
        'title': 'Сопровождение сайта', 'deadline': '01.11.2026 18:00',
    }, now=datetime(2026, 11, 27, tzinfo=UTC))
    assert result == 'OUT'
    assert 'application_deadline_expired' in reasons


def test_223_profile_preserves_law_and_support_queries():
    profile = load_daily_tender_profile('arvectum-it-223')
    assert profile.law == '223fz'
    assert 'сопровождение сайта' in profile.queries
    assert profile.remote_support_subject_keywords


@pytest.mark.parametrize('found', [True, False])
def test_explicit_223_lookup_never_calls_44_provider(found):
    from unittest.mock import Mock

    from src.tender_research.pipeline import TenderResearchPipeline
    from src.tender_research.providers.public_44fz_search import (
        PublicTenderSearchItem,
        PublicTenderSearchPage,
    )
    from src.tender_research.registry_discovery import SourceType

    number = '32616614845'
    pipeline = object.__new__(TenderResearchPipeline)
    pipeline._public_provider = Mock()
    pipeline._public_223fz_provider = Mock()
    pipeline._public_223fz_provider.search.return_value = PublicTenderSearchPage(
        items=[PublicTenderSearchItem(registry_number=number, law_type='223fz')] if found else [],
    )
    result = pipeline._lookup_public_discovered_item(number, law_type='223fz')
    pipeline._public_provider.search.assert_not_called()
    assert result.law_type == '223fz'
    assert result.source_type == SourceType.EXTERNAL_PUBLIC_223FZ


def test_companion_profile_runs_even_if_first_has_unresolved_errors(monkeypatch):
    from unittest.mock import MagicMock, Mock

    from scripts import run_daily_tender_run as cli

    session = MagicMock()
    monkeypatch.setattr(cli, 'SessionLocal', session)
    monkeypatch.setattr(cli, 'resume_pending_daily_tender_runs', Mock(return_value=[]))
    create = Mock(side_effect=lambda _session, request: request.profile_id)
    monkeypatch.setattr(cli, 'create_daily_tender_run', create)
    monkeypatch.setattr(cli, 'to_run_response', Mock(return_value=Mock(model_dump_json=Mock(return_value='{}'))))
    monkeypatch.setattr(cli, '_exit_code_with_diagnostic', Mock(side_effect=[20, 0]))
    assert cli._run_profiles(['arvectum-it', 'arvectum-it-223', 'arvectum-it']) == 20
    assert [c.args[1].profile_id for c in create.call_args_list] == ['arvectum-it', 'arvectum-it-223']
    assert session.call_count == 2
