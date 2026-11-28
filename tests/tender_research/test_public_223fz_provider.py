from __future__ import annotations

from unittest.mock import Mock

import pytest

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


_NUMBER = "12345678901"
_GUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_MODAL = ("https://zakupki.gov.ru/epz/order/notice/notice223/signview/listModal.html"
          f"?purchaseNoticeGuid={_GUID}&purchaseNoticeNumber={_NUMBER}")
_DOCS = ("https://zakupki.gov.ru/epz/order/notice/notice223/documents.html"
         f"?purchaseNoticeNumber={_NUMBER}&noticeGuid={_GUID}")
_FILE = "https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=" + "a" * 32


def test_signature_modal_is_resolved_to_number_guid_bound_documents(monkeypatch):
    body = f"<div class='data-block__value'>{_NUMBER}</div>" + _pair("Заказчик", "АО Тест") + f'<a href="{_FILE}">ТЗ.pdf</a>'
    provider = Public223FzSearchProvider()
    fetch = Mock(return_value={"status": PublicSearchStatus.SUCCESS, "html": body})
    monkeypatch.setattr(provider, "_fetch_page", fetch)
    detail = provider.fetch_detail(card_url=_MODAL, registry_number=_NUMBER)
    fetch.assert_called_once_with(_DOCS)
    assert detail.network_status == PublicSearchStatus.SUCCESS
    assert detail.registry_number == _NUMBER
    assert detail.card_url == _DOCS
    assert detail.raw["requires_review"] is True
    assert len(detail.document_links) == 1
    assert detail.document_links[0].raw["revision_review_required"] is True


@pytest.mark.parametrize("url", [
    _MODAL.replace(_NUMBER, "12345678902"),
    _MODAL.replace(_GUID, "unknown"),
    _MODAL.replace("zakupki.gov.ru", "evil.example"),
    _MODAL.replace("https://", "http://"),
    _MODAL.replace("zakupki.gov.ru", "zakupki.gov.ru:bad"),
    _MODAL + "&noticeGuid=" + _GUID,
    _MODAL + "&purchaseNoticeNumber=",
    _MODAL + "&regNumber=" + _NUMBER,
])
def test_signature_modal_unbound_rejected_before_network(monkeypatch, url):
    provider = Public223FzSearchProvider()
    fetch = Mock()
    monkeypatch.setattr(provider, "_fetch_page", fetch)
    detail = provider.fetch_detail(card_url=url, registry_number=_NUMBER)
    fetch.assert_not_called()
    assert detail.network_status == PublicSearchStatus.UNSUPPORTED_LAYOUT
    assert detail.document_links == []


def test_signature_modal_wrong_page_identity_rejected(monkeypatch):
    provider = Public223FzSearchProvider()
    fetch = Mock(return_value={"status": PublicSearchStatus.SUCCESS, "html": f'<a href="{_FILE}">ТЗ.pdf</a>'})
    monkeypatch.setattr(provider, "_fetch_page", fetch)
    detail = provider.fetch_detail(card_url=_MODAL, registry_number=_NUMBER)
    assert detail.network_status == PublicSearchStatus.UNSUPPORTED_LAYOUT
    assert detail.document_links == []


def test_223_search_preserves_literal_notice_guid_query():
    url = _MODAL.replace("purchaseNoticeGuid", "noticeGuid")
    fragment = f'<div class="registry-entry">Реестровый номер {_NUMBER}<a href="{url}">Подпись</a></div>'
    assert parse_223fz_search_results(fragment)[0].card_url == url


def test_bound_documents_filter_unofficial_and_ambiguous_links(monkeypatch):
    provider = Public223FzSearchProvider()
    body = _pair("Заказчик", "АО Тест") + _NUMBER + f'<a href="{_FILE}">ТЗ.pdf</a>'
    body += f'<a href="{_FILE.replace("zakupki.gov.ru", "evil.example")}">Подмена.pdf</a>'
    body += '<a href="https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=' + 'a' * 32 + '">44.pdf</a>'
    fetch = Mock(return_value={"status": PublicSearchStatus.SUCCESS, "html": body})
    monkeypatch.setattr(provider, "_fetch_page", fetch)
    detail = provider.fetch_detail(card_url=_DOCS, registry_number=_NUMBER)
    assert [link.url for link in detail.document_links] == [_FILE]
    assert detail.raw["requires_review"] is True
    fetch.return_value["html"] += " Редакция 1 Редакция 2"
    assert provider.fetch_detail(card_url=_MODAL, registry_number=_NUMBER).document_links == []
