"""Regression guards for source-bound 7z attachment extraction."""
import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_safe_7z import (
    _checked_entries,
    _valid_signature,
    stage_case,
)

LISTING = """
7-Zip listing
----------
Path = evidence.pdf
Size = 123
Attributes = A
Encrypted = -

Path = protocol.docx
Size = 456
Attributes = A
Encrypted = -
"""


def test_bounded_entries_accepts_regular_documents():
    entries = _checked_entries(LISTING)
    assert [e["declared_size"] for e in entries] == [123, 456]


@pytest.mark.parametrize("name", ["../escape.pdf", "/etc/a.pdf", "a\\b.pdf",
                                    "run.sh", "a:stream.pdf", ".hidden.pdf"])
def test_bounded_entries_refuses_unsafe_members(name):
    with pytest.raises(ValueError):
        _checked_entries(LISTING.replace("evidence.pdf", name))


def test_bounded_entries_refuses_encryption_and_size():
    with pytest.raises(ValueError):
        _checked_entries(LISTING.replace("Encrypted = -", "Encrypted = +"))
    with pytest.raises(ValueError):
        _checked_entries(LISTING.replace("Size = 123", "Size = 900000000"))


def test_signatures_are_strict():
    assert _valid_signature(b"%PDF-1.4", ".pdf")
    assert _valid_signature(b"PK\x03\x04other", ".docx")
    assert not _valid_signature(b"<html>forbidden", ".pdf")


def test_receipt_identity_required(tmp_path: Path):
    source = tmp_path / "32413297739"
    source.mkdir()
    (source / "public-page-receipt.json").write_text(json.dumps({
        "registry_number": "99999999999", "files": [],
    }))
    with pytest.raises(ValueError, match="Mismatched"):
        stage_case(source, tmp_path / "output")
