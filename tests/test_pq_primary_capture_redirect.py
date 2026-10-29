"""Redirect handling for immutable public-source capture (no network)."""
from contextlib import contextmanager

import pytest

from scripts.market_intelligence import capture_primary_source as capture


class Response:
    def __init__(self, status, location="", data=b""):
        self.status_code = status
        self.headers = {"location": location, "content-type": "application/octet-stream"}
        self.data = data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP failure")

    def iter_bytes(self):
        yield self.data


class Client:
    def __init__(self, responses, seen):
        self.responses = iter(responses)
        self.seen = seen

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    @contextmanager
    def stream(self, method, url, headers):
        self.seen.append(url)
        yield next(self.responses)


def test_relative_official_redirect_is_resolved_and_rechecked(monkeypatch):
    seen = []
    url = "https://bidzaar.com/api/filestorage/files/download/abc"
    monkeypatch.setattr(capture.httpx, "Client", lambda **_: Client([
        Response(302, "./abc/specification.docx"),
        Response(200, data=b"test-primary-docx-content"),
    ], seen))
    raw, content_type = capture.fetch(url)
    assert raw == b"test-primary-docx-content"
    assert content_type == "application/octet-stream"
    assert seen == [url, "https://bidzaar.com/api/filestorage/files/download/abc/specification.docx"]


def test_relative_redirect_to_untrusted_host_is_rejected(monkeypatch):
    seen = []
    url = "https://bidzaar.com/api/filestorage/files/download/abc"
    monkeypatch.setattr(capture.httpx, "Client", lambda **_: Client([
        Response(302, "//untrusted.invalid/steal"),
    ], seen))
    with pytest.raises(ValueError, match="allowlisted"):
        capture.fetch(url)
    assert seen == [url]
