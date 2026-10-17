"""Regression for intermittent EIS Varnish 404 with an authentic 200 page.

The retry is read-only, bounded, source-specific, and NEVER turns a persistent
404 into a closed/cancelled procurement status.
"""
from __future__ import annotations

import io
import ssl
from email.message import Message
from urllib.error import HTTPError

import pytest

from src.tender_research.providers import public_44fz_search as module

CZN_URL = (
    "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html"
    "?regNumber=0348100024426000039"
)
SEARCH_URL = "https://zakupki.gov.ru/epz/order/extendedsearch/results.html?fz44=on"
SUCCESS = (
    "<html><body><h1>Закупка № 0348100024426000039</h1>"
    "<div>Подача заявок</div></body></html>"
).encode()
NGINX_404 = b"<html><body><h1>404 Not Found</h1><center>nginx</center></body></html>"


def _error(url=CZN_URL, code=404, via="1.1 eis-varnish-pub01.zakupki.local (Varnish/7.7)",
           body=NGINX_404):
    hdrs = Message()
    if via:
        hdrs["Via"] = via
    hdrs["Content-Type"] = "text/html"
    return HTTPError(url, code, "upstream error", hdrs, io.BytesIO(body))


class _Page:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return SUCCESS


class _FakeOpener:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request.full_url, request.get_method(), timeout))
        answer = next(self.replies)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _prepare(monkeypatch, replies):
    opener = _FakeOpener(replies)
    waits = []
    handlers = []
    monkeypatch.setattr(module, "create_urllib_context", lambda _url: (ssl.create_default_context(), False))

    def fake_build_opener(*args):
        handlers.extend(args)
        return opener

    monkeypatch.setattr(module, "build_opener", fake_build_opener)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: waits.append(seconds))
    return module.Public44FzSearchProvider(timeout_seconds=3), opener, waits, handlers


def test_200_after_eis_pub01_404_recovered_without_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8080")
    provider, opener, waits, handlers = _prepare(monkeypatch, [_error(), _Page()])
    out = provider._fetch_page(CZN_URL)
    assert out["status"] == module.PublicSearchStatus.SUCCESS
    assert "0348100024426000039" in out["html"]
    assert out["eis_cache_retries"] == 1
    assert len(opener.calls) == 2
    assert all(method == "GET" for _, method, _ in opener.calls)
    assert waits == [module.EIS_NOTICE_EDGE_RETRY_BACKOFF_SECONDS]
    assert any(isinstance(h, module.ProxyHandler) and h.proxies == {} for h in handlers)


def test_two_cache_404s_then_success_bounded(monkeypatch):
    provider, opener, waits, _ = _prepare(monkeypatch, [_error(), _error(), _Page()])
    out = provider._fetch_page(CZN_URL)
    assert out["status"] == module.PublicSearchStatus.SUCCESS
    assert out["eis_cache_retries"] == 2
    assert len(opener.calls) == 3
    assert waits == [0.25, 0.5]


def test_persistent_eis_cache_404_fails_closed_not_cancelled(monkeypatch):
    provider, opener, waits, _ = _prepare(monkeypatch, [_error(), _error(), _error()])
    out = provider._fetch_page(CZN_URL)
    assert out["status"] == module.PublicSearchStatus.NETWORK_ERROR
    assert out["html"] is None
    assert "HTTP 404" in out["error"]
    assert "cache" in out["error"].lower()
    assert out["eis_cache_retries"] == 2
    assert len(opener.calls) == 3
    assert len(waits) == 2


@pytest.mark.parametrize("url,code,via,body", [
    (CZN_URL, 403, "1.1 eis-varnish-pub01.zakupki.local", NGINX_404),
    (CZN_URL, 429, "1.1 eis-varnish-pub01.zakupki.local", NGINX_404),
    (CZN_URL, 404, None, NGINX_404),
    (CZN_URL, 404, "1.1 eis-varnish-pub01.zakupki.local", b"An actual missing page"),
    (SEARCH_URL, 404, "1.1 eis-varnish-pub01.zakupki.local", NGINX_404),
])
def test_no_retry_without_exact_official_cached_nginx_signature(
    monkeypatch, url, code, via, body,
):
    provider, opener, waits, _ = _prepare(monkeypatch, [_error(url, code, via, body)])
    out = provider._fetch_page(url)
    assert out["status"] != module.PublicSearchStatus.SUCCESS
    assert len(opener.calls) == 1
    assert waits == []


def test_hostname_lookalike_rejected_before_request(monkeypatch):
    provider, opener, waits, _ = _prepare(monkeypatch, [])
    url = CZN_URL.replace("zakupki.gov.ru", "fakezakupki.gov.ru")
    out = provider._fetch_page(url)
    assert out["status"] == module.PublicSearchStatus.NETWORK_ERROR
    assert "not allowed" in out["error"]
    assert opener.calls == []
    assert waits == []
