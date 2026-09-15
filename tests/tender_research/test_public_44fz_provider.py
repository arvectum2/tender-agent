from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.tender_research.providers.public_44fz_search import (
    MAX_PAGE_SIZE,
    Public44FzSearchProvider,
    PublicSearchStatus,
    PublicTenderSearchItem,
    PublicTenderSearchPage,
    _classify_search_html,
    _normalize_law,
    parse_44fz_search_results,
)


class TestNormalizeLaw:
    def test_normalize_44fz(self):
        assert _normalize_law("44fz") == "44fz"
        assert _normalize_law("44FZ") == "44fz"
        assert _normalize_law("44-ФЗ") == "44fz"
        assert _normalize_law("44") == "44fz"

    def test_normalize_223fz(self):
        assert _normalize_law("223fz") == "223fz"
        assert _normalize_law("223FZ") == "223fz"

    def test_normalize_capital_repair(self):
        assert _normalize_law("capital_repair") == "capital_repair"
        assert _normalize_law("615") == "capital_repair"

    def test_default_unknown(self):
        assert _normalize_law("unknown") == "44fz"
        assert _normalize_law(None) == "44fz"


class TestPublicSearchStatus:
    def test_status_constants(self):
        assert PublicSearchStatus.SUCCESS == "success"
        assert PublicSearchStatus.BLOCKED == "blocked"
        assert PublicSearchStatus.TIMEOUT == "timeout"
        assert PublicSearchStatus.BAD_GATEWAY == "bad_gateway"


class TestClassifySearchHtml:
    def test_empty_html(self):
        assert _classify_search_html("") == "empty_results"
        assert _classify_search_html("   ") == "empty_results"

    def test_captcha_detected(self):
        html = "<html>recaptcha verification required</html>"
        assert _classify_search_html(html) == "captcha_or_blocked"

    def test_javascript_required(self):
        html = "<html>ваш браузер не поддерживает javascript</html>"
        assert _classify_search_html(html) == "captcha_or_blocked"

    def test_parsed_with_entry_marker(self):
        html = '<div class="registry-entry__body-value">Test</div>'
        assert _classify_search_html(html) == "parsed"

    def test_parsed_with_search_marker(self):
        html = "<html><body>Найдено 10 закупок</body></html>"
        assert _classify_search_html(html) == "parsed"

    def test_unsupported_layout(self):
        html = "<html><body>Some random page</body></html>"
        assert _classify_search_html(html) == "unsupported_layout"


class TestParse44FzSearchResults:
    def test_empty_html(self):
        assert parse_44fz_search_results("") == []

    def test_no_match(self):
        assert parse_44fz_search_results("<html></html>") == []

    def test_simple_card_extraction(self):
        html = """
        <div class="registry-entry">
            <div class="registry-entry__header-mid__title">Поставка оборудования</div>
        </div>
        """
        cards = parse_44fz_search_results(html)
        assert len(cards) > 0
        assert cards[0]["title"] is not None

    def test_fallback_extraction_by_number(self):
        html = """
        <html>
        <a href="https://zakupki.gov.ru/epz/order/notice/ea44/view/common-info.html?regNumber=0373200008225000004">link</a>
        </html>
        """
        cards = parse_44fz_search_results(html)
        assert len(cards) >= 1
        numbers = [c.get("reestr_number") for c in cards if c.get("reestr_number")]
        assert "0373200008225000004" in cards[0].get("reestr_number", "")


class TestPublic44FzProvider:
    def test_provider_initialization(self):
        provider = Public44FzSearchProvider(
            timeout_seconds=10,
            delay_seconds=0,
            bypass_proxy=True,
        )
        assert provider._timeout == 10
        assert provider._delay == 0
        assert provider._bypass_proxy is True

    def test_build_url_empty_query(self):
        provider = Public44FzSearchProvider()
        today = date.today()
        three_days_ago = today - timedelta(days=3)
        url = provider._build_url(
            query=None,
            date_from=three_days_ago,
            date_to=today,
            page=2,
            page_size=30,
        )
        assert "searchString" not in url
        assert "publishDateFrom=" in url
        assert "publishDateTo=" in url
        assert "pageNumber=2" in url
        assert "recordsPerPage=30" in url

    def test_build_url_with_query(self):
        provider = Public44FzSearchProvider()
        today = date.today()
        three_days_ago = today - timedelta(days=3)
        url = provider._build_url(
            query="серверное оборудование",
            date_from=three_days_ago,
            date_to=today,
            page=1,
            page_size=30,
        )
        assert "searchString=%D1%81%D0%B5%D1%80%D0%B2%D0%B5%D1%80%D0%BD%D0%BE%D0%B5" in url

    def test_build_url_defaults_dates(self):
        provider = Public44FzSearchProvider()
        url = provider._build_url(page=1, page_size=30)
        assert "publishDateFrom=" in url
        assert "publishDateTo=" in url

    def test_build_url_page_size_capped(self):
        provider = Public44FzSearchProvider()
        url = provider._build_url(page=1, page_size=200)
        assert f"recordsPerPage={MAX_PAGE_SIZE}" in url

    def test_build_url_law_flag(self):
        provider = Public44FzSearchProvider()
        url = provider._build_url(
            page=1,
            page_size=30,
            law_type="223fz",
        )
        assert "fz223=on" in url

    def test_extract_registry_numbers_empty(self):
        assert Public44FzSearchProvider.extract_registry_numbers([]) == []

    def test_extract_registry_numbers_from_items(self):
        page = PublicTenderSearchPage(
            items=[
                PublicTenderSearchItem(registry_number="0373200008225000004"),
                PublicTenderSearchItem(registry_number="0373200008225000005"),
            ],
            page=1,
            page_size=30,
        )
        numbers = Public44FzSearchProvider.extract_registry_numbers([page])
        assert numbers == ["0373200008225000004", "0373200008225000005"]

    def test_extract_registry_numbers_deduplicates(self):
        page = PublicTenderSearchPage(
            items=[
                PublicTenderSearchItem(registry_number="0373200008225000004"),
                PublicTenderSearchItem(registry_number="0373200008225000004"),
            ],
            page=1,
            page_size=30,
        )
        numbers = Public44FzSearchProvider.extract_registry_numbers([page])
        assert numbers == ["0373200008225000004"]

    def test_search_pages_empty_args(self):
        provider = Public44FzSearchProvider(timeout_seconds=5, delay_seconds=0)
        pages = provider.search_pages(max_pages=1, page_size=10)
        assert len(pages) >= 1
        assert pages[0].status in (PublicSearchStatus.SUCCESS, PublicSearchStatus.TIMEOUT, PublicSearchStatus.BLOCKED, PublicSearchStatus.BAD_GATEWAY)

    def test_card_to_item(self):
        card = {
            "title": "Поставка",
            "notice_number": "0373200008225000004",
            "reestr_number": "0373200008225000004",
            "customer_name": "Test",
            "initial_price": 5000000.0,
            "publication_date": "01.07.2026",
            "deadline": "01.08.2026",
        }
        item = Public44FzSearchProvider._card_to_item(card)
        assert item.registry_number == "0373200008225000004"
        assert item.title == "Поставка"
        assert item.nmck_amount == 5000000.0


class TestPublicTenderDataclasses:
    def test_public_tender_search_item_defaults(self):
        item = PublicTenderSearchItem()
        assert item.registry_number is None
        assert item.title is None

    def test_public_tender_search_item_with_data(self):
        item = PublicTenderSearchItem(
            registry_number="0373200008225000004",
            title="Test",
            nmck_amount=1000000.0,
        )
        assert item.registry_number == "0373200008225000004"
        assert item.title == "Test"
        assert item.nmck_amount == 1000000.0

    def test_public_tender_search_page_defaults(self):
        page = PublicTenderSearchPage()
        assert page.items == []
        assert page.page == 1
        assert page.page_size == 30
        assert page.status == PublicSearchStatus.SUCCESS

    def test_public_tender_search_page_with_data(self):
        page = PublicTenderSearchPage(
            items=[PublicTenderSearchItem(registry_number="0373200008225000004")],
            page=2,
            page_size=30,
            has_next=True,
            status=PublicSearchStatus.SUCCESS,
        )
        assert len(page.items) == 1
        assert page.page == 2
        assert page.has_next is True


def test_search_card_does_not_alias_placement_organization_to_customer():
    html = """
    <div class="registry-entry">
      <div class="registry-entry__header-mid__title">Оказание услуг</div>
      <div class="registry-entry__body-title">Организация, осуществляющая размещение</div>
      <div class="registry-entry__body-value">ГКУ Региональный центр закупок</div>
      <a href="/epz/order/notice/ea20/view/common-info.html?regNumber=0123456789012345678">0123456789012345678</a>
    </div>
    """

    cards = parse_44fz_search_results(html)

    assert len(cards) == 1
    assert cards[0]["customer_name"] is None
