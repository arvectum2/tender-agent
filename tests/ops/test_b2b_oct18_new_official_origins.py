"""Offline, no-network checks of new EIS attachment receipts and B2B primary."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.acceptance.audit_b2bcenter_oct18_primary import (
    DETAIL,
    INDEX,
    PrimaryMarketError,
    verify,
)
from scripts.acceptance.audit_eis_oct18_original_attachments import (
    NUMBERS,
    OriginalSourceError,
    docx_text,
    magic_match,
    official_filestore,
)

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/roadmap"
GOOD_URL = "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=x"


def _docx(main: bytes = b"<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:t>OK source</w:t></w:document>") -> bytes:
    file = io.BytesIO()
    with zipfile.ZipFile(file, "w") as z:
        z.writestr("word/document.xml", main)
    return file.getvalue()


def test_official_filestore_rejects_redirections_to_other_hosts_and_downgrades():
    assert official_filestore(GOOD_URL)
    for bad in (
        GOOD_URL.replace("https://", "http://", 1),
        GOOD_URL.replace("zakupki.gov.ru", "zakupki.gov.ru.evil.example"),
        GOOD_URL.replace("file.html", "wrong.html"),
        GOOD_URL.split("?")[0],
        GOOD_URL + "#fragment",
        GOOD_URL.replace("https://", "https://user:pass@", 1),
    ):
        assert not official_filestore(bad)


def test_docx_only_main_body_attested_not_attachments_or_rich_semantics():
    body = _docx()
    assert docx_text(body) == "OK source"
    assert magic_match("description.docx", body) == "DOCX_MAIN_BODY_OK"
    assert magic_match("legacy.doc", b"\xd0\xcf\x11\xe0" + b"dummy") == "LEGACY_DOC_OPAQUE_UNEXTRACTED"
    assert magic_match("raw.zip", body) == "ZIP_ORIGINAL_CONTAINER_UNEXTRACTED"


@pytest.mark.parametrize("name,body", [
    ("fake.docx", b"<html>falsified</html>"),
    ("doc.txt", b"nonsense"),
    ("contract.docx", b"PK\x03\x04" + b"invalid zip"),
    ("contract.docx", _docx(b"<!DOCTYPE foo><w:document />")),
    ("contract.docx", _docx(b"<bad xml")),
])
def test_invalid_or_ambiguous_source_files_rejected(name, body):
    with pytest.raises((OriginalSourceError, ValueError, zipfile.BadZipFile)):
        magic_match(name, body)


def test_original_eis_notice_source_replay_is_three_distinct_44fz_with_no_go():
    j = json.loads((DOCS / "b2b_oct18_three_new_eis_originals.json").read_text())
    assert j["audit_date"] == "2026-10-18"
    assert {r["number"] for r in j["records"]} == set(NUMBERS)
    assert len(j["records"]) == 3
    assert j["owner_bid_ready_count"] == 0
    assert j["current_legal_status_verified"] is False
    assert j["no_original_binaries_persisted"] is True
    for row in j["records"]:
        assert row["source_type"] == "OFFICIAL_EIS_SOAP_GETDOCSIP_ARCHIVED_ORIGINAL"
        assert row["archival_evidence"] == "SHA_VERIFIED_NOTICE"
        assert row["competitive_status"] == "ATTESTED_COMPETITIVE"
        assert row["current_live_legal_status_verified"] is False
        assert row["current_notice_latest_live_verified"] is False
        assert row["bid_ready"] is False
        assert len(row["zip_sha256"]) == len(row["original_xml_sha256"]) == 64
        assert datetime.fromisoformat(row["source_archived_end_dt"]).utcoffset() is not None


def test_firstparty_official_binary_receipts_are_hash_bound_without_signed_urls():
    notices = json.loads((DOCS / "b2b_oct18_three_new_eis_originals.json").read_text())
    prior = {row["number"]: row for row in notices["records"]}
    current = json.loads((DOCS / "b2b_oct18_three_official_attachments.json").read_text())
    assert current["fixed_allowlist"] == list(NUMBERS)
    assert current["total_official_fetched_binary_attachments"] == 17
    assert current["temporary_original_files_discarded"]
    assert current["exact_source_url_query_never_disclosed"]
    assert current["legal_live_status_verified"] is False
    assert current["fully_qualifying_current_bids"] == 0
    assert current["commercial_bid_actions"] == 0
    assert len(current["entries"]) == 3
    for entry in current["entries"]:
        assert entry["registry_number"] in prior
        assert entry["original_notice_version"] == prior[entry["registry_number"]]["selected_archived_version"]
        assert entry["zip_sha256"] == prior[entry["registry_number"]]["zip_sha256"]
        assert entry["notice_xml_sha256"] == prior[entry["registry_number"]]["original_xml_sha256"]
        assert len(entry["files"]) == entry["official_attached_files"] > 0
        assert entry["all_document_semantics_verified"] is False
        assert entry["company_eligibility_verified"] is False
        assert entry["bid_ready"] is False
        for original in entry["files"]:
            assert len(original["binary_sha256"]) == 64
            assert len(original["source_url_sha256"]) == 64
            assert original["binary_size"] > 0
            assert original["only_docx_main_body_scanned"] is True
            assert original["other_content_or_nested_attachments_unchecked"] is True
            assert "https:" not in json.dumps(original)
            assert "priz/file.html" not in json.dumps(original)
            assert original["format_status"] in (
                "DOCX_MAIN_BODY_OK", "LEGACY_DOC_OPAQUE_UNEXTRACTED",
                "ZIP_ORIGINAL_CONTAINER_UNEXTRACTED",
            )


def _index() -> bytes:
    return f'<a href="{DETAIL}">4643484</a><div>ТЕХ ВЗРЫВ ИНВЕСТ</div>'.encode()


def _detail() -> bytes:
    return (
        "Разработка корпоративного сайта под ключ с обязательным предоставлением реализованных кейсов "
        "и коммерческих предложений — Тендер № 4643484 — АО ТЕХ ВЗРЫВ ИНВЕСТ "
        "до 21.10.2026 06:00, по МСК"
    ).encode()


def test_b2bcenter_firstparty_pair_never_promoted_to_bid_eligibility():
    result = verify(_index(), _detail(), observed_at=datetime(2026, 10, 18, tzinfo=UTC))
    assert result["official_category_index"] == INDEX
    assert result["exact_platform_detail_url"] == DETAIL
    assert result["registry_number"] == "4643484"
    assert result["public_original_listing_seen"] is True
    assert result["buyer_go_or_bid_ready"] is False
    assert result["platform_fees_confirmed_for_this_bid"] is False
    assert result["full_commercial_specification_verified"] is False


@pytest.mark.parametrize("a,b", [
    (b"not original", _detail()),
    (_index(), b"not original"),
    (_index(), _detail().replace(b"4643484", b"bad")),
    (_index(), _detail().replace(b"21.10.2026", b"30.10.2026")),
])
def test_b2bcenter_primary_source_tampering_fails_closed(a, b):
    with pytest.raises(PrimaryMarketError):
        verify(a, b, observed_at=datetime(2026, 10, 18, tzinfo=UTC))


def test_source_checkpoints_unambiguous_and_still_not_ready():
    x = json.loads((DOCS / "b2b_oct18_b2bcenter_4643484_firstparty.json").read_text())
    assert x["registry_number"] == "4643484"
    assert x["exact_platform_detail_url"] == DETAIL
    assert x["original_printed_deadline_moscow"] == "2026-10-21T06:00:00+03:00"
    assert x["buyer_go_or_bid_ready"] is False
    assert x["platform_business_account_entitlement_verified"] is False
    assert x["payment_or_external_message"] is False
    assert len(x["index_html_sha256"]) == len(x["detail_html_sha256"]) == 64
