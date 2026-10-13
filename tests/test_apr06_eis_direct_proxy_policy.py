"""Regressions for direct official EIS urllib access despite environment proxies."""
from __future__ import annotations

from urllib.request import ProxyHandler

from src.shared.network.http_client import create_urllib_opener


def test_official_eis_direct_opener_ignores_environment_proxy(monkeypatch):
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9999")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9998")
    monkeypatch.setenv("all_proxy", "http://127.0.0.1:9997")
    url = "https://zakupki.gov.ru/epz/main/public/home.html"

    opener = create_urllib_opener(
        url,
        source_direct_connection=True,
        follow_redirects=False,
    )

    proxy_handlers = [x for x in opener.handlers if isinstance(x, ProxyHandler)]
    assert len(proxy_handlers) == 1
    assert proxy_handlers[0].proxies == {}


def test_eis_no_redirect_opener_has_no_proxy_handlers_from_environment(monkeypatch):
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9999")
    url = "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html"

    opener = create_urllib_opener(
        url,
        source_direct_connection=True,
        follow_redirects=False,
    )

    assert all(
        not getattr(h, "proxies", None)
        for h in opener.handlers
        if isinstance(h, ProxyHandler)
    )
