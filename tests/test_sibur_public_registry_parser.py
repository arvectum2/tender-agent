import json

import pytest

from src.modules.tender_connectors.sibur.parser import HEADERS, page_url, parse_page


def fixture(page=1, rows=None):
    if rows is None:
        rows = [["1234567/1", "Equipment", "Spec", "Request", "14.11.2026",
                 "19.11.2026 09:00:00", "Buyer", "Open", "PRIVATE NAME",
                 "PRIVATE PHONE", "PRIVATE EMAIL", "Category", "Doc"]]
    head = "<tr>" + "".join(f"<th>{v}</th>" for v in HEADERS) + "</tr>"
    body = "".join("<tr>" + "".join(f"<td>{v}<div>Развернуть</div></td>" for v in row)
                   + "</tr>" for row in rows)
    content = '<table class="table__table">' + head + body + "</table>"
    pagination = (f'<a class="_current pagination__items-item">{page}</a>'
                  '<a class="pagination__items-item">27</a>')
    return json.dumps({"content": content, "pagination": pagination}).encode()


def test_source_and_privacy():
    page = parse_page(fixture(2), 2)
    assert (page.page, page.last_page) == (2, 27)
    record = page.records[0]
    assert record["external_id"] == "1234567/1"
    assert record["deadline_raw"] == "19.11.2026 09:00:00"
    assert record["source_url"] == page_url(2)
    assert record["source_sha256"] == page.sha256
    assert "PRIVATE" not in str(record)
    assert record["verification"] == "PUBLIC_SNAPSHOT_ONLY"


def test_wrong_page_and_shape_fail_closed():
    with pytest.raises(ValueError):
        parse_page(fixture(2), 1)
    with pytest.raises(ValueError):
        parse_page(b'{"content":"", "pagination":""}', 1)
    with pytest.raises(ValueError):
        parse_page(fixture(rows=[["1234567/1"]]), 1)


def test_duplicate_id_preserves_both_source_observations():
    row = ["1234567/1", "Title"] + ["x"] * 11
    variant = row.copy()
    variant[-1] = "Additional document"
    result = parse_page(fixture(rows=[row, variant]), 1)
    assert len(result.records) == 2
    assert result.records[0]["external_id"] == result.records[1]["external_id"]
    assert [r["source_row"] for r in result.records] == ["1", "2"]
    assert [r["documentation_label"] for r in result.records] == ["x", "Additional document"]


@pytest.mark.parametrize("page", [0, -1, 1001, True, "1"])
def test_page_validation(page):
    with pytest.raises(ValueError):
        page_url(page)


def test_bounded_capture_preserves_duplicates_and_reports_partial(tmp_path, monkeypatch):
    from io import BytesIO
    from urllib.parse import parse_qs, urlsplit

    from scripts.research import capture_sibur_public_snapshot as capture

    class FakeOpener:
        def open(self, request, timeout):
            n = int(parse_qs(urlsplit(request.full_url).query)["PAGEN_1"][0])
            return BytesIO(fixture(n))

    monkeypatch.setattr(capture.urllib.request, "build_opener", lambda *a: FakeOpener())
    monkeypatch.setattr(capture.time, "sleep", lambda _: None)
    root = tmp_path / "capture"
    report = capture.collect(root, 2)
    assert report["raw_rows"] == 2
    assert report["unique_ids"] == report["repeated_ids"] == 1
    assert not report["advertised_pages_traversed"]
    records = json.loads((root / "normalized.json").read_text())
    assert len(records[0]["observations"]) == 2
    assert report["repeated"][0]["varying_fields"] == []


def test_bounded_capture_rejects_bad_shape(tmp_path, monkeypatch):
    from io import BytesIO

    from scripts.research import capture_sibur_public_snapshot as capture

    class FakeOpener:
        def open(self, request, timeout):
            return BytesIO(b"not-json")

    monkeypatch.setattr(capture.urllib.request, "build_opener", lambda *a: FakeOpener())
    root = tmp_path / "capture"
    report = capture.collect(root, 2)
    assert report["validated_pages"] == 0
    assert report["errors"]
    assert not report["advertised_pages_traversed"]
    assert (root / "page-001.json").read_bytes() == b"not-json"


def test_attachment_scope():
    payload = json.loads(fixture())
    payload["content"] = payload["content"].replace(
        "Doc<div>",
        '<a href="/upload/tmp/example/a.pdf">Allowed</a>'
        '<a href="https://invalid.example/x.pdf">Foreign</a>'
        '<a href="/upload/tmp/example/b.pdf?token=x">Query</a>'
        '<a href="javascript:alert(1)">Script</a>'
        '<div>',
    )
    row = parse_page(json.dumps(payload).encode(), 1).records[0]
    assert row["documentation_urls"] == ["https://www.sibur.ru/upload/tmp/example/a.pdf"]
    assert row["unverified_document_links"] == 3
