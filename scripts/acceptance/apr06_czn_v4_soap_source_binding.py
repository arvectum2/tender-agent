"""Offline integrity audit: original EIS getDocsIP ZIP -> current notice XML -> UID receipts.

This binds names, byte lengths, publishedContentId and original HTTPS URLs to
previously separately hashed local-file receipts. It does not verify a digital
signature, procurement eligibility, or complete internal ZIP document contents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

_MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
_MAX_XML_BYTES = 4 * 1024 * 1024
_MAX_MEMBERS = 120
_MAX_TOTAL_UNCOMPRESSED = 30 * 1024 * 1024
_UID = re.compile(r"[0-9A-F]{32}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")


def _name(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _first(node: ET.Element, name: str) -> str | None:
    return next(
        (child.text.strip() for child in node.iter() if _name(child) == name and child.text),
        None,
    )


def _parse_original_xml(raw: bytes, reg: str) -> dict | None:
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("XML DTD/entity is forbidden")
    root = ET.fromstring(raw)
    notices = [node for node in root if _name(node).startswith("epNotification")]
    if not notices:
        return None
    if len(notices) != 1:
        raise ValueError("Multiple XML notices")
    node = notices[0]
    version = _first(node, "versionNumber")
    if not version or not version.isdecimal() or int(version) < 1:
        raise ValueError("Invalid original notice version")
    if _first(node, "purchaseNumber") != reg:
        raise ValueError("Original notice registry mismatch")
    items = []
    for attachment in node.iter():
        if _name(attachment) != "attachmentInfo":
            continue
        uid = _first(attachment, "publishedContentId")
        size = _first(attachment, "fileSize")
        filename = _first(attachment, "fileName")
        source_url = _first(attachment, "url")
        if not uid or not _UID.fullmatch(uid) or not filename or not size or not size.isdecimal():
            raise ValueError("Invalid original attachment metadata")
        url = urlsplit(source_url or "")
        if (
            url.scheme != "https"
            or url.hostname != "zakupki.gov.ru"
            or url.port is not None
            or url.path != "/44fz/filestore/public/1.0/download/priz/file.html"
            or parse_qs(url.query).get("uid") != [uid]
        ):
            raise ValueError("Original attachment URL/UID mismatch")
        items.append((uid, filename, int(size)))
    if len({item[0] for item in items}) != len(items):
        raise ValueError("Duplicate attachment UID")
    if len({(item[1], item[2]) for item in items}) != len(items):
        raise ValueError("Duplicate attachment name/size")
    return {
        "version": int(version),
        "xml_sha256": hashlib.sha256(raw).hexdigest(),
        "xml_bytes": len(raw),
        "published_at": _first(node, "publishDTInEIS"),
        "deadline": _first(node, "endDT"),
        "notice_type": _name(node),
        "items": items,
    }


def audit_soap_source(archive_path: Path, manifest: dict) -> dict:
    """Raise on ANY XML/UID/size/hash receipt mismatch; never infer human approval."""
    if manifest.get("schema_version") != "apr06-czn-v4-public-html-source-receipt-v1":
        raise ValueError("Unexpected original receipt schema")
    reg = manifest.get("reg_number")
    if reg != "0348100024426000039":
        raise ValueError("Wrong target case")
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ValueError("Missing regular original SOAP archive")
    if archive_path.stat().st_size > _MAX_ARCHIVE_BYTES:
        raise ValueError("SOAP archive too large")
    raw = archive_path.read_bytes()
    archive_sha = hashlib.sha256(raw).hexdigest()
    bound = manifest.get("official_soap_original")
    if not isinstance(bound, dict) or not _SHA.fullmatch(bound.get("archive_sha256", "")):
        raise ValueError("Missing pinned original SOAP archive digest")
    if archive_sha != bound["archive_sha256"] or len(raw) != bound.get("archive_bytes"):
        raise ValueError("Original SOAP archive changed")
    notices = []
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if not members or len(members) > _MAX_MEMBERS:
            raise ValueError("Unexpected member count")
        if sum(member.file_size for member in members) > _MAX_TOTAL_UNCOMPRESSED:
            raise ValueError("Excessive uncompressed archive size")
        seen = set()
        for member in members:
            name = Path(member.filename)
            if (
                member.is_dir()
                or name.is_absolute()
                or ".." in name.parts
                or len(name.parts) != 1
                or name.suffix.lower() != ".xml"
                or member.filename in seen
                or member.file_size > _MAX_XML_BYTES
                or stat.S_ISLNK(member.external_attr >> 16)
                or member.flag_bits & 1
            ):
                raise ValueError("Unexpected or unsafe original SOAP ZIP member")
            seen.add(member.filename)
            doc = _parse_original_xml(archive.read(member), reg)
            if doc is not None:
                notices.append(doc)
    if not notices or len({n["version"] for n in notices}) != len(notices):
        raise ValueError("Missing or duplicate notice version")
    latest = max(notices, key=lambda n: n["version"])
    if latest["version"] != 4 or latest["notice_type"] != "epNotificationEOK2020":
        raise ValueError("Original latest notice is not expected EOK v4")
    if latest["xml_sha256"] != bound.get("version_4_xml_sha256"):
        raise ValueError("Original v4 XML bytes changed")
    if latest["xml_bytes"] != bound.get("version_4_xml_bytes"):
        raise ValueError("Original v4 XML size changed")
    if latest["deadline"] != manifest["official_public_html_evidence"]["application_deadline_msk"]:
        raise ValueError("Original SOAP notice and current HTML deadline disagree")
    expected = {
        (row["uid"], row["file_name"], row["size_bytes"])
        for row in manifest.get("files", [])
        if _UID.fullmatch(row["uid"]) and _SHA.fullmatch(row["sha256"])
    }
    if len(expected) != 7 or len(manifest["files"]) != 7:
        raise ValueError("Incomplete or duplicate locally hashed UID receipts")
    if set(latest["items"]) != expected or len(latest["items"]) != 7:
        raise ValueError("Original EIS v4 UID/name/size differs from saved local file receipts")
    return {
        "archive_sha256": archive_sha,
        "latest_original_xml_sha256": latest["xml_sha256"],
        "latest_original_xml_bytes": latest["xml_bytes"],
        "latest_original_version": latest["version"],
        "published_at_original": latest["published_at"],
        "deadline_original": latest["deadline"],
        "version_count": len(notices),
        "original_uid_name_size_receipt_matches": len(expected),
        "digital_signature_validated": False,
        "internal_zip_documents_reviewed": False,
        "human_gold_labels": 0,
        "commercial_accepted": False,
        "status": "SOAP_ORIGINAL_UID_SIZE_RECEIPTS_CORRELATED_NOT_SIGNED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    result = audit_soap_source(
        args.archive, json.loads(args.manifest.read_text(encoding="utf-8"))
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
