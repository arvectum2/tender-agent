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


def test_strict_curl_transport_rejects_redirect(monkeypatch, tmp_path):
    import subprocess
    from pathlib import Path

    def fake_run(cmd, **_):
        assert '--noproxy' in cmd and '--proto' in cmd
        assert cmd[cmd.index('--proto') + 1] == '=https'
        Path(cmd[cmd.index('--output') + 1]).write_bytes(b'fake content' * 10)
        return subprocess.CompletedProcess(cmd, 0, '302\ntext/html\nhttps://www.roseltorg.ru/procedure/COM1', '')

    monkeypatch.setattr(capture.subprocess, 'run', fake_run)
    with pytest.raises(RuntimeError, match='not exact URL HTTP 200'):
        capture.fetch_curl_direct('https://www.roseltorg.ru/procedure/COM1')


def test_strict_curl_transport_accepts_only_verified_exact_source(monkeypatch):
    import subprocess
    from pathlib import Path
    url = 'https://com.roseltorg.ru/file/get/t/LotDocuments/id/4476617'

    def fake_run(cmd, **_):
        Path(cmd[cmd.index('--output') + 1]).write_bytes(b'original-doc' * 12)
        return subprocess.CompletedProcess(cmd, 0, '200\napplication/msword\n' + url, '')

    monkeypatch.setattr(capture.subprocess, 'run', fake_run)
    raw, kind = capture.fetch_curl_direct(url)
    assert raw == b'original-doc' * 12
    assert kind == 'application/msword'


def test_sibur_official_archive_and_document_allowed_but_lookalikes_rejected():
    assert capture.source_url('https://sibur.ru/ru/procurement/buy/archive/?procedure=2129455%2F1')
    assert capture.source_url('https://sibur.ru/upload/tmp/example/059/spec.docx')
    with pytest.raises(ValueError, match='allowlisted'):
        capture.source_url('https://sibur.ru.evil.example/ru/procurement/buy/archive/')
    with pytest.raises(ValueError, match='allowlisted'):
        capture.source_url('http://sibur.ru/ru/procurement/buy/archive/')


def test_official_kuzbass_regulator_pdf_allowed_without_widening_host_boundary():
    url = "https://www.recko.ru/files/doc/20250324140802_82.pdf"
    assert capture.source_url(url) == url
    with pytest.raises(ValueError, match="allowlisted"):
        capture.source_url("https://www.recko.ru.attacker.example/files/doc/20250324140802_82.pdf")
    with pytest.raises(ValueError, match="allowlisted"):
        capture.source_url("http://www.recko.ru/files/doc/20250324140802_82.pdf")
