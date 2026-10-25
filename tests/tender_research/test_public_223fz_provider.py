from __future__ import annotations

from src.tender_research.providers.public_44fz_search import PublicSearchStatus
from src.tender_research.providers.public_223fz_search import (
    Public223FzSearchProvider,
    parse_223fz_detail,
    parse_223fz_search_results,
)


def _pair(label: str, value: str) -> str:
    return f'<div class="registry-entry__body-title">{label}</div><div class="registry-entry__body-value">{value}</div>'


def test_parse_223fz_normal_card_and_documents():
    body = '<div class="registry-entry">Реестровый номер 12345678901234567890' + _pair("Наименование закупки", "Кабель") + _pair("Заказчик", "АО Тест") + '<a href="/epz/order/notice/file/download.html?id=7">ТЗ.pdf</a></div>'
    item = parse_223fz_search_results(body)[0]
    assert item.registry_number == "12345678901234567890"
    assert item.law_type == "223fz"
    assert item.customer_name == "АО Тест"
    detail = parse_223fz_detail(body, "https://zakupki.gov.ru/notice/1", item.registry_number)
    assert detail.document_links[0].url.startswith("https://zakupki.gov.ru/")
    assert detail.raw["requires_review"] is False


def test_parse_223fz_missing_customer_fails_closed():
    body = "Реестровый номер 12345678901234567890" + _pair("Наименование закупки", "Кабель")
    detail = parse_223fz_detail(body, "https://zakupki.gov.ru/notice/1")
    assert detail.customer_name is None
    assert detail.raw["requires_review"] is True
    assert "customer_role_not_explicit" in detail.raw["review_reasons"]


def test_parse_223fz_ambiguous_revision_fails_closed():
    body = "Реестровый номер 12345678901234567890 Редакция 1 Редакция 2" + _pair("Заказчик", "АО Тест")
    detail = parse_223fz_detail(body, "https://zakupki.gov.ru/notice/1")
    assert detail.raw["requires_review"] is True
    assert "revision_state_ambiguous" in detail.raw["review_reasons"]


def test_223fz_provider_never_falls_back_without_detail_url():
    detail = Public223FzSearchProvider().fetch_detail(registry_number="12345678901234567890")
    assert detail.network_status == PublicSearchStatus.UNSUPPORTED_LAYOUT
    assert detail.law_type == "223fz"
    assert "no 44-FZ fallback" in (detail.error_message or "")


def test_unrecognized_223fz_html_must_not_be_reported_as_success():
    body = "<html><body>Иная вёрстка без явно обозначенных полей ЕИС</body></html>"
    detail = parse_223fz_detail(body, "https://example.org/unrecognized", "32616445866")
    assert detail.network_status == PublicSearchStatus.UNSUPPORTED_LAYOUT
    assert detail.raw["requires_review"] is True
    assert "unrecognized_223fz_detail_layout" in detail.raw["review_reasons"]


def test_223fz_document_navigation_is_not_a_download():
    body = (
        _pair("Заказчик", "АО Тест")
        + '<a href="/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=123">Документы</a>'
        + '<a href="https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=ABCD">ТЗ.docx</a>'
    )
    detail = parse_223fz_detail(body, "https://zakupki.gov.ru/epz/order/notice/notice223/documents.html", "123")
    assert len(detail.document_links) == 1
    assert "filestore" in detail.document_links[0].url


def test_real_eis_tooltip_with_embedded_html_yields_safe_file_extension():
    html = (
        _pair("Заказчик", "АО Тест")
        + '<a href="https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=ABCDEF1234567890ABCDEF1234567890" '
        + """data-tooltip='<span class="custom-tooltiptext">26-004167 ЗД.zip</span>' >26-004167 ЗД</a>"""
    )
    detail = parse_223fz_detail(html, "https://zakupki.gov.ru/epz/order/notice/notice223/documents.html", "32615969197")
    assert len(detail.document_links) == 1
    assert detail.document_links[0].file_name == "26-004167 ЗД.zip"
    assert detail.document_links[0].raw["filename_from_official_tooltip"] is True


def test_223fz_file_anchor_plain_text_fallback_without_tooltip():
    html = _pair("Заказчик", "АО Тест") + (
        '<a href="/223/purchase/public/download/download.html?id=1234">Документ.pdf</a>'
    )
    detail = parse_223fz_detail(html, "https://zakupki.gov.ru/notice/1", "32313008364")
    assert [ref.file_name for ref in detail.document_links] == ["Документ.pdf"]
