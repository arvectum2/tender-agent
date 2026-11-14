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
