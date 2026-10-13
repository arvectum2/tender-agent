"""Source-anchored tests for independent EIS original archive verification."""
from __future__ import annotations

import hashlib
import zipfile

import pytest

from scripts.acceptance.audit_r5_official_sources import (
    audit_archive,
    parse_notice,
    reconcile,
)

NUMBER = "0372200172326000015"
OTHER = "0158300034526000388"


def notice(version: int, number: str = NUMBER, *, deadline: str = "2026-10-16T10:00:00+03:00") -> bytes:
    return (
        '<export><epNotificationEZK2020>'
        f'<versionNumber>{version}</versionNumber>'
        '<nested><versionNumber>33</versionNumber></nested>'
        f'<commonInfo><purchaseNumber>{number}</purchaseNumber></commonInfo>'
        f'<endDT>{deadline}</endDT><maxPrice>100.00</maxPrice>'
        '<maxPrice>100.0</maxPrice></epNotificationEZK2020></export>'
    ).encode()


def test_nested_version_does_not_override_notice_version():
    result = parse_notice(notice(2), NUMBER)
    assert len(result) == 1
    assert result[0]["version"] == 2
    assert result[0]["maxPrice"] == "100.00"
    assert result[0]["endDT"] == "2026-10-16T10:00:00+03:00"


def test_ignores_foreign_registry_number():
    assert parse_notice(notice(5, OTHER), NUMBER) == []


def test_reject_unsafe_xml_external_entities():
    with pytest.raises(ValueError, match="unsafe_or_oversized_xml"):
        parse_notice(b"<!DOCTYPE root [<!ENTITY x SYSTEM 'file:///etc/passwd'>]><root/>", NUMBER)


def test_reject_ambiguous_direct_revision():
    raw = notice(1).replace(b"<versionNumber>1</versionNumber>",
                             b"<versionNumber>1</versionNumber><versionNumber>2</versionNumber>", 1)
    with pytest.raises(ValueError, match="ambiguous_notice_version"):
        parse_notice(raw, NUMBER)


def test_zip_uses_highest_official_notice_revision(tmp_path):
    p = tmp_path / "archive.zip"
    with zipfile.ZipFile(p, "w") as archive:
        archive.writestr("one.xml", notice(1, deadline="2026-10-14T10:00:00+03:00"))
        archive.writestr("three.xml", notice(3))
    proof = audit_archive(p, NUMBER)
    assert proof["archived_versions"] == [1, 3]
    assert proof["highest"]["version"] == 3
    assert proof["highest"]["endDT"] == "2026-10-16T10:00:00+03:00"
    assert hashlib.sha256(notice(1, deadline="2026-10-14T10:00:00+03:00")).hexdigest() in proof["sha_map"]


def test_reconcile_detects_stale_receipt_and_preserves_unknown_approval(tmp_path):
    folder = tmp_path / NUMBER
    folder.mkdir()
    old = notice(1, deadline="2026-10-14T10:00:00+03:00")
    latest = notice(3)
    with zipfile.ZipFile(folder / "documentation-archive.zip", "w") as archive:
        archive.writestr("old.xml", old)
        archive.writestr("new.xml", latest)
    zhash = hashlib.sha256((folder / "documentation-archive.zip").read_bytes()).hexdigest()
    receipts = [{"reg_number": NUMBER, "notice_sha256": hashlib.sha256(old).hexdigest(),
                 "document_files": [{"sha256": hashlib.sha256(old).hexdigest()}]}]
    transport = {"cases": [{"reg_number": NUMBER, "transport": "completed",
                            "fresh_official_zip_sha256": zhash, "zip_same_as_prior": True}]}
    stored = {"cases": [{"reg_number": NUMBER, "raw_file_matched": 1,
                         "raw_file_mismatches": [], "stored_report": True,
                         "stored_recommendation": "participate_conditionally"}]}
    output = reconcile(receipts, transport, tmp_path, stored)
    assert len(output) == 1
    assert output[0]["old_notice_archived_version"] == 1
    assert output[0]["last_archived_version"] == 3
    assert output[0]["selected_notice_stale_vs_archive"] is True
    assert output[0]["technical_disposition"] == "HISTORICAL_RECEIPT_OLDER_THAN_ARCHIVE"
    assert output[0]["human_signoff"] is False
