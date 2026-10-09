"""Actual 223-FZ attachment provider must be selected, with fail-closed source reviews."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.modules.tender_operator_agent_demo import procurement_intake_service as service


def test_223_source_uses_correct_parser_and_preserves_download_source(monkeypatch):
    calls = []

    class Fake223:
        def __init__(self, *, bypass_proxy):
            assert bypass_proxy
            calls.append("223")

        def fetch_detail(self, *, card_url):
            assert "/223/" in card_url
            return SimpleNamespace(
                raw={"source_regime": "223fz", "requires_review": False},
                document_links=[
                    SimpleNamespace(
                        title="ТЗ", file_name="Техническое задание.docx",
                        url="https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=ABC",
                        raw={"source_regime": "223fz"},
                    ),
                ],
            )

    monkeypatch.setattr(service, "Public223FzSearchProvider", Fake223)
    monkeypatch.setattr(service, "Public44FzSearchProvider", lambda **kwargs: pytest.fail("44-FZ used for 223-FZ"))
    attachments = service._fetch_public_notice_attachments(
        "https://zakupki.gov.ru/223/purchase/public/purchase/info/documents.html?purchaseNoticeNumber=32616197376&noticeGuid=c41a69d6-cd15-4723-8674-b992f1b6b31e",
    )
    assert calls == ["223"]
    assert len(attachments) == 1
    assert attachments[0].extension == ".docx"
    assert attachments[0].can_download is True


def test_223_ambiguous_revision_must_not_download(monkeypatch):
    class Fake223:
        def __init__(self, **kwargs):
            pass

        def fetch_detail(self, **kwargs):
            return SimpleNamespace(
                raw={"requires_review": True, "review_reasons": ["revision_state_ambiguous"]},
                document_links=[
                    SimpleNamespace(title="ТЗ", file_name="a.docx", url="https://zakupki.gov.ru/223/file", raw={})
                ],
            )

    monkeypatch.setattr(service, "Public223FzSearchProvider", Fake223)
    with pytest.raises(service.PublicRevisionBindingError, match="revision_state_ambiguous"):
        service._fetch_public_notice_attachments(
            "https://zakupki.gov.ru/223/purchase/public/purchase/info/documents.html?purchaseNoticeNumber=32616197376&noticeGuid=c41a69d6-cd15-4723-8674-b992f1b6b31e",
        )


def test_44_source_stays_on_44_parser(monkeypatch):
    class Fake44:
        def __init__(self, **kwargs):
            pass

        def fetch_detail(self, **kwargs):
            return SimpleNamespace(
                raw={"document_revision_selection": {"requires_review": False}},
                document_links=[],
            )

    monkeypatch.setattr(service, "Public44FzSearchProvider", Fake44)
    monkeypatch.setattr(service, "Public223FzSearchProvider", lambda **kwargs: pytest.fail("223-FZ parser on 44-FZ"))
    assert service._fetch_public_notice_attachments(
        "https://zakupki.gov.ru/epz/order/notice/zk20/documents.html?regNumber=0372200172326000015"
    ) == []

def test_223_document_link_is_read_from_official_common_info_and_requires_guid():
    html = (
        '<a href="/epz/order/notice/notice223/documents.html?'
        'purchaseNoticeNumber=32616197376&noticeGuid=c41a69d6-cd15-4723-8674-b992f1b6b31e">'
        'Документы</a>'
    )
    result = service._extract_223fz_documents_navigation_url(
        html, notice_number="32616197376",
    )
    assert result.endswith(
        "purchaseNoticeNumber=32616197376&noticeGuid=c41a69d6-cd15-4723-8674-b992f1b6b31e"
    )
    assert "¬iceGuid" not in result
    assert service._extract_223fz_documents_navigation_url(
        html, notice_number="32616263956",
    ) is None


def test_223_multiple_guids_fail_closed():
    template = (
        '<a href="/epz/order/notice/notice223/documents.html?'
        'purchaseNoticeNumber=32616197376&noticeGuid={}">Документы</a>'
    )
    html = template.format("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa") + template.format("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    with pytest.raises(service.PublicRevisionBindingError, match="multiple official"):
        service._extract_223fz_documents_navigation_url(
            html, notice_number="32616197376",
        )


def test_223_official_navigation_resolution_uses_real_guid(monkeypatch):
    seen = []

    class Fake223:
        def __init__(self, *, bypass_proxy):
            assert bypass_proxy

        def fetch_detail(self, *, card_url):
            seen.append(card_url)
            if card_url.endswith("common-info.html?regNumber=32616197376"):
                return SimpleNamespace(common_info_html=(
                    '<a href="/epz/order/notice/notice223/documents.html?'
                    'purchaseNoticeNumber=32616197376&amp;noticeGuid='
                    'c41a69d6-cd15-4723-8674-b992f1b6b31e">Документы</a>'
                ))
            return SimpleNamespace(
                raw={"requires_review": False},
                document_links=[],
            )

    monkeypatch.setattr(service, "Public223FzSearchProvider", Fake223)
    assert service._fetch_public_notice_attachments(
        "https://zakupki.gov.ru/223/purchase/public/purchase/info/documents.html?regNumber=32616197376",
    ) == []
    assert len(seen) == 2
    assert "noticeGuid=" in seen[1]
    assert "purchaseNoticeNumber=32616197376" in seen[1]


def test_223_html_fragment_file_name_recovers_real_extension_without_unsafe_allowlist(monkeypatch):
    class Fake223:
        def __init__(self, **kwargs):
            pass

        def fetch_detail(self, **kwargs):
            return SimpleNamespace(
                raw={"requires_review": False},
                document_links=[
                    SimpleNamespace(
                        title="Извещение", file_name="Извещение.pdf ' > Извещение",
                        url="https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=ABC",
                        raw={"source_regime": "223fz"},
                    ),
                    SimpleNamespace(
                        title="Документация",
                        file_name="Извещение о закупке у ед.поставщика.docx ' > Извещение",
                        url="https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=DEF",
                        raw={"source_regime": "223fz"},
                    ),
                ],
            )

    monkeypatch.setattr(service, "Public223FzSearchProvider", Fake223)
    docs=service._fetch_public_notice_attachments(
        "https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?"
        "purchaseNoticeNumber=32616197376&noticeGuid=c41a69d6-cd15-4723-8674-b992f1b6b31e"
    )
    assert [doc.extension for doc in docs] == [".pdf", ".docx"]
    assert [doc.name for doc in docs] == ["Извещение.pdf", "Извещение о закупке у ед.поставщика.docx"]


def test_223_direct_url_rejects_spoofed_notice_guid_or_wrong_host():
    for url in (
        (
            "https://zakupki.gov.ru/223/purchase/public/purchase/info/documents.html?"
            "purchaseNoticeNumber=32616197376&noticeGuid=not-a-uuid"
        ),
        (
            "https://evil.example/223/purchase/public/purchase/info/documents.html?"
            "purchaseNoticeNumber=32616197376&noticeGuid=c41a69d6-cd15-4723-8674-b992f1b6b31e"
        ),
    ):
        with pytest.raises(service.PublicRevisionBindingError):
            service._resolve_223fz_documents_url(url)
