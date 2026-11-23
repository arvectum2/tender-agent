import hashlib
import json

import pytest

from src.modules.tender_connectors.sibur.archive_parser import (
    CATEGORIES,
    archive_page,
    archive_url,
    replay_archived_page,
)
from src.modules.tender_connectors.sibur.parser import HEADERS


def fixture(category="107", last=1075):
    row=["1234567/1","Equipment","Spec","Request","14.11.2026","19.11.2026 09:00",
         "Buyer","Прием предложений завершен","PRIVATE NAME","PRIVATE PHONE","PRIVATE EMAIL",
         CATEGORIES[category][1],'<a href="/upload/tmp/example/a.pdf">Doc</a>']
    head="<tr>"+"".join(f"<th>{v}</th>" for v in HEADERS)+"</tr>"
    body="<tr>"+"".join(f"<td>{v}</td>" for v in row)+"</tr>"
    return json.dumps({"content":'<table class="table__table">'+head+body+"</table>",
                       "pagination":'<a class="_current pagination__items-item">1</a>'
                                    +f'<a class="pagination__items-item">{last}</a>'}).encode()


def test_archive_source_large_paginator_and_privacy():
    result=archive_page(fixture(), "107", 1)
    assert result.last_page==1075
    row=result.records[0]
    assert row["source_url"]==archive_url("107",1)
    assert "/archive/" in row["source_url"]
    assert "PRIVATE" not in str(row)
    assert row["status_raw"]=="Прием предложений завершен"
    assert row["documentation_urls"]==["https://www.sibur.ru/upload/tmp/example/a.pdf"]


def test_filter_and_page_mismatch():
    with pytest.raises(ValueError,match="category"):
        archive_page(fixture(), "108", 1)
    with pytest.raises(ValueError,match="pagination"):
        archive_page(fixture(), "107", 2)
    with pytest.raises(ValueError):
        archive_url("unverified",1)


@pytest.mark.parametrize("category", list(CATEGORIES))
def test_each_admitted_source_category_is_explicitly_bounded(category):
    parsed = archive_page(fixture(category=category, last=42), category, 1)
    assert parsed.page == 1
    assert parsed.last_page == 42
    assert len(parsed.records) == 1
    assert parsed.records[0]["source"] == "sibur_public"
    assert parsed.records[0]["documentation_urls"] == [
        "https://www.sibur.ru/upload/tmp/example/a.pdf"
    ]


def test_duplicate_first_party_json_keys_fail_closed():
    raw = fixture()
    data = json.loads(raw)
    tampered = json.dumps(data).replace('{"content":', '{"content":"untrusted","content":')
    with pytest.raises(ValueError, match="duplicate SIBUR source JSON member"):
        archive_page(tampered.encode(), "107", 1)


def test_reject_outbound_document_links_without_promoting_to_original():
    raw = fixture().replace(b"/upload/tmp/example/a.pdf", b"https://evil.example/a.pdf")
    parsed = archive_page(raw, "107", 1)
    assert parsed.records[0]["documentation_urls"] == []
    assert parsed.records[0]["unverified_document_links"] == 1


def test_archive_source_page_type_and_limit_rejected():
    for page in (0, -1, "1", 10001, True):
        with pytest.raises(ValueError, match="category/page"):
            archive_url("107", page)
    for source in (b"", b"[]", b"{invalid json}"):
        with pytest.raises((ValueError, json.JSONDecodeError)):
            archive_page(source, "107", 1)


def test_page_identity_must_match_original_current_page():
    raw = fixture()
    with pytest.raises(ValueError, match="pagination"):
        archive_page(raw, "107", 2)


def archive_source_fixture(tmp_path, *, category="107"):
    raw = fixture(category=category)
    sha = hashlib.sha256(raw).hexdigest()
    original = tmp_path / f"p00001-{sha}.raw.json"
    original.write_bytes(raw)
    receipt = {
        "category": category, "page": 1, "url": archive_url(category, 1),
        "file": original.name, "sha256": sha, "rows": 1,
        "last_page": 1075, "ids": ["1234567/1"],
        "observed_at": "2026-11-15T10:00:00Z",
    }
    (tmp_path / "p00001.json").write_text(json.dumps(receipt))
    return original, receipt


def test_byte_pinned_original_archive_receipt_replay(tmp_path):
    archive_source_fixture(tmp_path)
    page = replay_archived_page(tmp_path, "107", 1)
    assert page.page == 1 and page.last_page == 1075
    assert [r["external_id"] for r in page.records] == ["1234567/1"]


def test_changed_original_archive_bytes_fail_closed(tmp_path):
    original, _ = archive_source_fixture(tmp_path)
    original.write_bytes(original.read_bytes() + b" ")
    with pytest.raises(ValueError, match="bytes hash mismatch"):
        replay_archived_page(tmp_path, "107", 1)


def test_reordered_identity_or_wrong_category_fails(tmp_path):
    _, receipt = archive_source_fixture(tmp_path)
    receipt["ids"] = ["different"]
    (tmp_path / "p00001.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="parsed members disagree"):
        replay_archived_page(tmp_path, "107", 1)
    with pytest.raises(ValueError, match="original archived page identity"):
        replay_archived_page(tmp_path, "108", 1)


def test_traversal_file_name_refused(tmp_path):
    _, receipt = archive_source_fixture(tmp_path)
    receipt["file"] = "../outside.raw.json"
    (tmp_path / "p00001.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="original archived page identity"):
        replay_archived_page(tmp_path, "107", 1)


def test_linked_original_source_bytes_rejected(tmp_path):
    original, _ = archive_source_fixture(tmp_path)
    original.unlink()
    original.symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="missing or unsafe"):
        replay_archived_page(tmp_path, "107", 1)


def test_duplicate_fields_in_original_receipt_rejected(tmp_path):
    archive_source_fixture(tmp_path)
    receipt = tmp_path / "p00001.json"
    receipt.write_text(receipt.read_text().replace('{"category":', '{"category":"wrong","category":'))
    with pytest.raises(ValueError, match="duplicate SIBUR source JSON member"):
        replay_archived_page(tmp_path, "107", 1)
