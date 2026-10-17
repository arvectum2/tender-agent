"""Offline simulated TLS fetch failure; never fetch a real EIS or Tendigo page."""
from __future__ import annotations

import hashlib
from urllib.error import URLError

import pytest

from scripts.acceptance import capture_r4_preregistered_discovery as capture
from src.modules.tender_operator_agent_demo.r4_prospective_sampling import (
    preregister_sampling_intent,
)


def plan():
    return preregister_sampling_intent(
        registered_at_utc="2026-10-14T21:37:05+00:00",
        existing_blind_lock_sha256="a" * 64, target_new_cases=3,
    )


def test_network_blocker_creates_zero_cases_or_fake_source(monkeypatch, tmp_path):
    def unavailable(*_args, **_kwargs):
        raise URLError("handshake timeout")

    monkeypatch.setattr(capture, "urlopen", unavailable)
    receipt = capture.snapshot_preregistered_pages(plan(), tmp_path / "failed")
    assert receipt["verified_source_pages"] == 0
    assert receipt["candidate_numbers"] == []
    assert receipt["official_eis_originals_verified"] == 0
    assert receipt["human_gold_created"] == 0
    assert all(p["status"] == "SOURCE_UNAVAILABLE" for p in receipt["pages"])
    assert not list((tmp_path / "failed").rglob("*.html"))


def test_html_original_sha_bound_to_tls_response_fixture(monkeypatch, tmp_path):
    class MockResponse:
        status = 200
        def __init__(self, url):
            self.url = url
            self.headers = {"Content-Type": "text/html; charset=utf-8"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def geturl(self):
            return self.url

        def read(self, _limit):
            return b"<html><body>" + b"x" * 130 + b"</body></html>"

    monkeypatch.setattr(capture, "urlopen", lambda request, **_kw: MockResponse(request.full_url))
    root = tmp_path / "pass"
    result = capture.snapshot_preregistered_pages(plan(), root)
    assert result["verified_source_pages"] == 2
    for r in result["pages"]:
        raw = (root / r["html_file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == r["content_sha256"]
    with pytest.raises(ValueError, match="overwrite"):
        capture.snapshot_preregistered_pages(plan(), root)


def test_future_registered_intent_never_backdated(monkeypatch, tmp_path):
    later = preregister_sampling_intent(
        registered_at_utc="2099-01-01T00:00:00+00:00",
        existing_blind_lock_sha256="a" * 64, target_new_cases=3,
    )
    with pytest.raises(ValueError, match="future"):
        capture.snapshot_preregistered_pages(later, tmp_path / "future")
