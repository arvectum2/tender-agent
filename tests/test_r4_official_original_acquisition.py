"""Synthetic first-party binary source receipt tests. Not legal conclusions."""
from __future__ import annotations

import hashlib

import pytest

from src.modules.tender_operator_agent_demo.r4_official_original_acquisition import (
    retrieve_original_binary,
)


def item():
    return {
        "publishedContentId": "id_123",
        "fileName": "specification.pdf",
        "fileSize": "7",
        "url": "https://zakupki.gov.ru/api/file/123",
    }

def fetch(_url, _size):
    return b"PDFdata"

def test_exact_sha_original_download_does_not_require_text_parsing(tmp_path):
    result=retrieve_original_binary(uid="id_123",source_item=item(),source_root=tmp_path,fetch=fetch)
    assert result["status"]=="FIRST_PARTY_BINARY_VERIFIED"
    assert result["sha256"]==hashlib.sha256(b"PDFdata").hexdigest()
    assert (tmp_path/"id_123.pdf").read_bytes()==b"PDFdata"
    with pytest.raises(ValueError,match="overwrite"):
        retrieve_original_binary(uid="id_123",source_item=item(),source_root=tmp_path,fetch=fetch)

@pytest.mark.parametrize("mutation",[
    lambda d:d.update(url="http://zakupki.gov.ru/api/file/123"),
    lambda d:d.update(url="https://example.org/api/file/123"),
    lambda d:d.update(fileSize="-10"),
    lambda d:d.update(fileSize="500000000"),
    lambda d:d.update(fileName="payload.exe"),
    lambda d:d.update(publishedContentId="different"),
])
def test_source_spoofing_and_unbounded_original_rejected(tmp_path,mutation):
    row=item();mutation(row)
    with pytest.raises(ValueError):
        retrieve_original_binary(uid="id_123",source_item=row,source_root=tmp_path,fetch=fetch)

def test_substituted_length_fails_without_persisting_binary(tmp_path):
    with pytest.raises(ValueError,match="declared size"):
        retrieve_original_binary(uid="id_123",source_item=item(),source_root=tmp_path,
                                 fetch=lambda _url,_size:b"wrong")
    assert not list(tmp_path.iterdir())
