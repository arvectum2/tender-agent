"""Operator's secondary public HTML reader must survive intermittent EIS edge 404."""
from __future__ import annotations

import io
from email.message import Message
from urllib.error import HTTPError

from src.modules.tender_operator_agent_demo import procurement_intake_service as service

NOTICE = (
    "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html"
    "?regNumber=0348100024426000039"
)


def _http_error(code: int = 404):
    headers = Message()
    headers["Via"] = "1.1 eis-varnish-pub01.zakupki.local (Varnish/7.7)"
    return HTTPError(
        NOTICE,
        code,
        "upstream response",
        headers,
        io.BytesIO(b"<html><h1>404 Not Found</h1><p>nginx</p></html>"),
    )


class _HtmlResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return (
            '<html><body><span class="section__title">Дата и время окончания срока '
            'подачи заявок</span><span class="section__info">23.10.2026 10:00</span>'
            '<p>Подача заявок, 0348100024426000039</p></body></html>'
        ).encode("utf-8")


class _Opener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def open(self, request, timeout):
        self.calls += 1
        assert request.get_method() == "GET"
        assert timeout == 20
        val = next(self.responses)
        if isinstance(val, Exception):
            raise val
        return val


def test_operator_public_context_retries_known_pub01_404(monkeypatch):
    opener = _Opener([_http_error(), _HtmlResponse()])
    waits = []
    monkeypatch.setattr(service, "create_urllib_opener", lambda url, source_direct_connection: opener)
    monkeypatch.setattr(service.time, "sleep", lambda sec: waits.append(sec))
    context = service._extract_public_page_context(NOTICE)
    assert "deadline" in context
    assert context["deadline"]
    assert opener.calls == 2
    assert waits == [0.25]


def test_operator_public_context_fails_closed_after_bounded_retries(monkeypatch):
    opener = _Opener([_http_error(), _http_error(), _http_error()])
    monkeypatch.setattr(service, "create_urllib_opener", lambda url, source_direct_connection: opener)
    monkeypatch.setattr(service.time, "sleep", lambda _: None)
    assert service._extract_public_page_context(NOTICE) == {}
    assert opener.calls == 3


def test_operator_public_context_does_not_retry_rate_limit(monkeypatch):
    opener = _Opener([_http_error(429)])
    monkeypatch.setattr(service, "create_urllib_opener", lambda url, source_direct_connection: opener)
    assert service._extract_public_page_context(NOTICE) == {}
    assert opener.calls == 1


def test_operator_context_rejects_host_lookalike_before_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Untrusted host must not trigger network")
    monkeypatch.setattr(service, "create_urllib_opener", forbidden)
    assert service._extract_public_page_context(
        NOTICE.replace("zakupki.gov.ru", "notzakupki.gov.ru")
    ) == {}
    assert service._infer_public_documents_url(
        NOTICE.replace("zakupki.gov.ru", "notzakupki.gov.ru")
    ) is None
