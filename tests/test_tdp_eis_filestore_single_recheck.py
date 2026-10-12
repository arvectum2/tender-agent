"""Offline bounded recheck cases: no real requests, no cached file writes."""
from __future__ import annotations

import hashlib

import pytest

from scripts.ops.recheck_eis_filestore_receipt import (
    recheck_entry,
    verify_receipt_entry,
)
from src.modules.tender_operator_agent_demo.attachment_downloader import (
    AttachmentTransportError,
)

UID = "01A10C59B0B8791B8D464C4C14D10A94"
URL = "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=" + UID
RAW = b"sample original"


def receipt():
    return {"uid": UID, "url": URL, "sha256": hashlib.sha256(RAW).hexdigest(),
            "size_bytes": len(RAW)}


def test_exact_bytes_verified_once():
    calls = []
    def transport(url, bound):
        calls.append((url, bound))
        return RAW, "application/octet-stream"
    output = recheck_entry(receipt(), transport=transport)
    assert output["result"] == "verified"
    assert output["source_binary_verified"] is True
    assert len(calls) == 1


@pytest.mark.parametrize("status", [404, 429])
def test_rate_limit_and_not_found_fail_closed_without_retry(status):
    calls = []
    def transport(_url, _bound):
        calls.append(1)
        raise AttachmentTransportError(f"http_status:{status}")
    output = recheck_entry(receipt(), transport=transport)
    assert output == {"result": "unavailable", "reason": f"http_status:{status}",
                      "source_binary_verified": False}
    assert len(calls) == 1


@pytest.mark.parametrize("raw", [b"different", RAW+b"x"])
def test_mismatch_is_not_accepted(raw):
    out = recheck_entry(receipt(), transport=lambda *_: (raw, None))
    assert out["result"] == "mismatch"
    assert out["source_binary_verified"] is False


@pytest.mark.parametrize("bad_url", [
    "https://evil.example/44fz/filestore/public/1.0/download/priz/file.html?uid="+UID,
    "http://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid="+UID,
    URL+"&other=1",
    URL.replace(UID, "A"*32),
    "https://zakupki.gov.ru.evil.example/44fz/filestore/public/1.0/download/priz/file.html?uid="+UID,
])
def test_untrusted_url_rejected_before_network(bad_url):
    entry = receipt()
    entry["url"] = bad_url
    with pytest.raises(ValueError):
        verify_receipt_entry(entry)


@pytest.mark.parametrize("bad_size", [0, -1, 31*1024*1024, "10", True])
def test_invalid_size_rejected(bad_size):
    entry = receipt()
    entry["size_bytes"] = bad_size
    with pytest.raises(ValueError):
        verify_receipt_entry(entry)
