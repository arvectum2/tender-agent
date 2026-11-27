from unittest.mock import Mock

import pytest

from src.modules.tender_operator_agent_demo import public_44fz_parser as parser
from src.tender_research.browser.eis_playwright_worker import (
    _same_search,
    is_eis_search_url,
)

URL = 'https://zakupki.gov.ru/epz/order/extendedsearch/results.html?searchString=test&fz223=on'
ZERO = '<div class="search-results__total">0 записей</div><div class="search-registry-entrys-block"></div><p class="noRecords">Поиск не дал результатов</p>'


@pytest.mark.parametrize('status', ['timeout', 'bad_gateway', 'parse_error', 'js_heavy'])
def test_fallback_for_non_security_failure(monkeypatch, status):
    monkeypatch.setenv('ARVECTUM_EIS_PLAYWRIGHT_PYTHON', '/isolated/python')
    monkeypatch.setattr(parser, '_get_provider', lambda: Mock(_fetch_page=Mock(return_value={'status': status})))
    browser = Mock(return_value={'status': 'ok', 'html': ZERO})
    monkeypatch.setattr(parser, 'fetch_eis_browser', browser)
    result = parser.fetch_public_44fz_search_page(URL)
    browser.assert_called_once_with(URL, '/isolated/python')
    assert result['explicit_zero_count'] is True
    assert result['fetcher'] == 'playwright'


@pytest.mark.parametrize('status', ['blocked', 'captcha_or_blocked', 'network_error'])
def test_security_failure_does_not_try_browser(monkeypatch, status):
    monkeypatch.setenv('ARVECTUM_EIS_PLAYWRIGHT_PYTHON', '/isolated/python')
    monkeypatch.setattr(parser, '_get_provider', lambda: Mock(_fetch_page=Mock(return_value={'status': status})))
    browser = Mock()
    monkeypatch.setattr(parser, 'fetch_eis_browser', browser)
    assert parser.fetch_public_44fz_search_page(URL)['status'] == status
    browser.assert_not_called()


def test_unverified_browser_empty_does_not_erase_primary_failure(monkeypatch):
    monkeypatch.setenv('ARVECTUM_EIS_PLAYWRIGHT_PYTHON', '/isolated/python')
    monkeypatch.setattr(parser, '_get_provider', lambda: Mock(_fetch_page=Mock(return_value={'status': 'timeout'})))
    monkeypatch.setattr(parser, 'fetch_eis_browser', Mock(return_value={'status': 'ok', 'html': ''}))
    assert parser.fetch_public_44fz_search_page(URL)['status'] == 'timeout'


def test_valid_empty_does_not_launch_browser(monkeypatch):
    monkeypatch.setenv('ARVECTUM_EIS_PLAYWRIGHT_PYTHON', '/isolated/python')
    monkeypatch.setattr(parser, '_get_provider', lambda: Mock(_fetch_page=Mock(return_value={'status': 'success', 'html': ZERO})))
    browser = Mock()
    monkeypatch.setattr(parser, 'fetch_eis_browser', browser)
    assert parser.fetch_public_44fz_search_page(URL)['explicit_zero_count']
    browser.assert_not_called()


@pytest.mark.parametrize('url', ['https://evil.test/epz/order/extendedsearch/results.html?q=x', 'http://zakupki.gov.ru/epz/order/extendedsearch/results.html?q=x', 'https://zakupki.gov.ru/epz/lk/?q=x', 'https://a@zakupki.gov.ru/epz/order/extendedsearch/results.html?q=x'])
def test_public_search_url_boundary(url):
    assert not is_eis_search_url(url)


def test_browser_cannot_change_search_regime():
    assert is_eis_search_url(URL)
    assert _same_search(URL, URL)
    assert not _same_search(URL, URL.replace('fz223=on', 'fz44=on'))
