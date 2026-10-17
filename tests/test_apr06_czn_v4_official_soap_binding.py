"""Offline adversarial tests for getDocsIP original v4 XML and public file receipts."""
from __future__ import annotations

import copy
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from scripts.acceptance.apr06_czn_v4_soap_source_binding import audit_soap_source

SOURCE = (Path(__file__).resolve().parents[1]
          / "docs/acceptance/apr06_czn_v4_public_eis_source_receipts_2026-10-13.json")


def _notice_xml(manifest: dict, *, version: int, mutate: str | None = None) -> bytes:
    root = ET.Element("export")
    notice = ET.SubElement(root, "epNotificationEOK2020")
    ET.SubElement(notice, "versionNumber").text = str(version)
    common = ET.SubElement(notice, "commonInfo")
    ET.SubElement(common, "purchaseNumber").text = manifest["reg_number"]
    ET.SubElement(common, "publishDTInEIS").text = (
        "2026-10-12T22:24:55.431+03:00"
    )
    info = ET.SubElement(notice, "notificationInfo")
    ET.SubElement(info, "endDT").text = (
        "2026-10-22T10:00:00+03:00" if mutate == "deadline"
        else "2026-10-23T10:00:00+03:00"
    )
    attachments = ET.SubElement(notice, "attachmentsInfo")
    if version == 4:
        for idx, row in enumerate(manifest["files"]):
            att = ET.SubElement(attachments, "attachmentInfo")
            ET.SubElement(att, "publishedContentId").text = (
                "F" * 32 if mutate == "uid" and idx == 0 else row["uid"]
            )
            ET.SubElement(att, "fileName").text = row["file_name"]
            ET.SubElement(att, "fileSize").text = str(row["size_bytes"])
            ET.SubElement(att, "url").text = (
                "https://fakezakupki.gov.ru/44fz/filestore/public/1.0/download/"
                f"priz/file.html?uid={row['uid']}"
                if mutate == "host" and idx == 0 else
                "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/"
                f"priz/file.html?uid={row['uid']}"
            )
    return ET.tostring(root, encoding="utf-8")


def _make_archive(tmp_path: Path, manifest: dict, *, mutate: str | None = None,
                  bad_filename: bool = False, duplicate_version: bool = False):
    p = tmp_path / "archive.zip"
    v4_xml = _notice_xml(manifest, version=4, mutate=mutate)
    with zipfile.ZipFile(p, "w") as archive:
        for version in (1, 2, 3, 4):
            name = "../notice_4.xml" if bad_filename and version == 4 else f"notice_{version}.xml"
            archive.writestr(
                name, v4_xml if version == 4 else
                _notice_xml(manifest, version=version)
            )
        if duplicate_version:
            archive.writestr("extra.xml", _notice_xml(manifest, version=4))
    manifest["official_soap_original"] = {
        "archive_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "archive_bytes": p.stat().st_size,
        "version_4_xml_sha256": hashlib.sha256(v4_xml).hexdigest(),
        "version_4_xml_bytes": len(v4_xml),
    }
    return p


def _manifest() -> dict:
    return copy.deepcopy(json.loads(SOURCE.read_text(encoding="utf-8")))


def test_signed_indeterminate_realistic_original_uid_correlation(tmp_path):
    manifest = _manifest()
    archive = _make_archive(tmp_path, manifest)
    result = audit_soap_source(archive, manifest)
    assert result["status"] == "SOAP_ORIGINAL_UID_SIZE_RECEIPTS_CORRELATED_NOT_SIGNED"
    assert result["latest_original_version"] == 4
    assert result["original_uid_name_size_receipt_matches"] == 7
    assert result["digital_signature_validated"] is False
    assert result["human_gold_labels"] == 0
    assert result["commercial_accepted"] is False


def test_corrupted_soap_archive_refused_even_when_zip_opens(tmp_path):
    manifest = _manifest()
    archive = _make_archive(tmp_path, manifest)
    raw = archive.read_bytes()
    archive.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    with pytest.raises(ValueError, match="archive changed"):
        audit_soap_source(archive, manifest)


@pytest.mark.parametrize("mutation,error", [
    ("uid", "URL/UID mismatch"),
    ("host", "URL/UID mismatch"),
    ("deadline", "deadline disagree"),
])
def test_forged_or_conflicting_original_xml_fails_closed(tmp_path, mutation, error):
    manifest = _manifest()
    archive = _make_archive(tmp_path, manifest, mutate=mutation)
    with pytest.raises(ValueError, match=error):
        audit_soap_source(archive, manifest)


def test_archive_member_traversal_refused(tmp_path):
    manifest = _manifest()
    archive = _make_archive(tmp_path, manifest, bad_filename=True)
    with pytest.raises(ValueError, match="unsafe"):
        audit_soap_source(archive, manifest)


def test_ambiguous_same_version_refused(tmp_path):
    manifest = _manifest()
    archive = _make_archive(tmp_path, manifest, duplicate_version=True)
    with pytest.raises(ValueError, match="duplicate notice"):
        audit_soap_source(archive, manifest)


def test_manifest_mismatch_is_not_human_approved(tmp_path):
    manifest = _manifest()
    archive = _make_archive(tmp_path, manifest)
    manifest["files"][0]["size_bytes"] += 1
    with pytest.raises(ValueError, match="differs"):
        audit_soap_source(archive, manifest)
