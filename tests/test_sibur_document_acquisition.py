import json

import pytest

from scripts.research.acquire_sibur_documents import (
    source_refs,
    type_matches,
    valid_url,
)
from src.modules.tender_connectors.sibur.parser import HEADERS, parse_page


def test_origin_constraints():
    good = "https://www.sibur.ru/upload/tmp/example/a.docx"
    assert valid_url(good)
    for url in (good + "?token=x", good + "#x", good.replace("www.sibur.ru", "example.com"),
                good.replace("https:", "http:"), good.replace("a.docx", "../a.docx")):
        assert not valid_url(url)


def test_signature():
    assert type_matches(b"%PDF-1.7", ".pdf")
    assert type_matches(b"PK\x03\x04", ".docx")
    assert not type_matches(b"<html>", ".pdf")
    assert not type_matches(b"PK\x03\x04", ".rar")


def test_verified_source_links(tmp_path):
    row = ["1234567/1", "Test"] + ["x"] * 10 + [
        '<a href="/upload/tmp/example/a.pdf">Doc</a>']
    content = '<table class="table__table"><tr>' + "".join(f"<th>{h}</th>" for h in HEADERS) + (
        "</tr><tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr></table>")
    raw = json.dumps({"content": content, "pagination":
                      '<a class="_current pagination__items-item">1</a>'}).encode()
    page = parse_page(raw, 1)
    (tmp_path / "page-001.json").write_bytes(raw)
    (tmp_path / "receipts.json").write_text(json.dumps({
        "advertised_pages_traversed": True, "errors": [],
        "pages": [{"page": 1, "sha256": page.sha256}]}))
    refs = source_refs(tmp_path)
    assert refs["https://www.sibur.ru/upload/tmp/example/a.pdf"][0]["external_id"] == "1234567/1"
    (tmp_path / "page-001.json").write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="receipt mismatch"):
        source_refs(tmp_path)


def test_priority_changes_order_without_excluding_others():
    from scripts.research.acquire_sibur_documents import order_candidates

    refs = {
        "https://www.sibur.ru/upload/tmp/example/a.pdf": [{"external_id": "other"}],
        "https://www.sibur.ru/upload/tmp/example/b.xlsx": [{"external_id": "priority"}],
        "https://www.sibur.ru/upload/tmp/example/c.rar": [{"external_id": "priority"}],
    }
    ordered = order_candidates(refs, {"priority"})
    assert ordered == [
        "https://www.sibur.ru/upload/tmp/example/b.xlsx",
        "https://www.sibur.ru/upload/tmp/example/a.pdf",
        "https://www.sibur.ru/upload/tmp/example/c.rar",
    ]


def test_capture_only_signatures_not_execution():
    assert type_matches(bytes.fromhex("d0cf11e0a1b11ae1"), ".doc")
    assert type_matches(b"Rar!\x1a\x07\x01", ".rar")
    assert type_matches(b"7z\xbc\xaf\x27\x1c", ".7z")
    assert type_matches(b"PK\x03\x04", ".xlsm")
    assert not type_matches(b"<html>", ".xls")
    assert not type_matches(b"MZ", ".exe")
