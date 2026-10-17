"""Safely inspect one application-level notice after an official EIS final protocol.

A notice for a different application is not evidence of procurement cancellation,
nor evidence that the company's original final rating has been recomputed.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

AKSAY = "0158300034526000388"
OUR_APP = "122031738"
OTHER_APP = "122034518"
ZIP_SHA = "d25187191599e705427676cc9de64ce665029381efa2490607d65ff237837bb8"
FINAL_XML_SHA = "2b9f510c48e7d828c432e32b4dca3a4fff8edb75c66c3da37d46a12af3456af5"
NOTICE_XML_SHA = "915b237acdaeeee201b445d6ba3a77ec5bb7520ecafe7038d9753529c2aba4f5"
MAX_XML_BYTES = 8 * 1024 * 1024


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def field(element: ET.Element, name: str) -> str | None:
    values = {(node.text or "").strip() for node in element.iter()
              if local_name(node.tag) == name and len(node) == 0}
    if len(values) > 1:
        raise ValueError(f"Ambiguous {name} in source XML")
    return next(iter(values), None)


def read_xml(archive: ZipFile, prefix: str, expected_sha: str) -> ET.Element:
    names = [name for name in archive.namelist()
             if name.startswith(prefix) and name.endswith(".xml")]
    if len(names) != 1:
        raise ValueError("Expected exactly one source XML for " + prefix)
    info = archive.getinfo(names[0])
    if not 0 < info.file_size <= MAX_XML_BYTES:
        raise ValueError("Unsafe source XML length")
    raw = archive.read(names[0])
    if sha256(raw).hexdigest() != expected_sha:
        raise ValueError("Original XML SHA mismatch for " + prefix)
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("XML entities are not allowed")
    return ET.fromstring(raw)


def parse_time(value: str | None) -> datetime:
    if not value:
        raise ValueError("Missing EIS publication timestamp")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("EIS timestamp must have explicit timezone")
    return dt


def audit_aksay_postfinal(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_XML_BYTES:
        raise ValueError("Missing or unsafe EIS archive")
    archive_sha = sha256(path.read_bytes()).hexdigest()
    if archive_sha != ZIP_SHA:
        raise ValueError("Official Aksay archive ZIP SHA mismatch")
    with ZipFile(path) as archive:
        final = read_xml(archive, "epProtocolEZK2020Final_" + AKSAY, FINAL_XML_SHA)
        notice = read_xml(archive, "epNoticeApplicationCancel_" + AKSAY, NOTICE_XML_SHA)
    if field(final, "purchaseNumber") != AKSAY or field(notice, "purchaseNumber") != AKSAY:
        raise ValueError("Mismatched procurement reference")
    final_at = parse_time(field(final, "publishDTInEIS"))
    notice_at = parse_time(field(notice, "docPublishDTInEIS"))
    if notice_at <= final_at:
        raise ValueError("Notice does not follow original final protocol")

    found: dict[str, tuple[str | None, str | None, str | None]] = {}
    for node in final.iter():
        if local_name(node.tag) != "applicationInfo":
            continue
        number = field(node, "appNumber")
        if not number or number in found:
            raise ValueError("Duplicate or missing appNumber in original final")
        found[number] = (field(node, "appRating"), field(node, "finalPrice"), field(node, "admitted"))
    if len(found) != 55:
        raise ValueError("Unexpected historical application count")
    if found.get(OUR_APP) != ("38", "119000", "true"):
        raise ValueError("Arvectum original app result not intact")
    if field(notice, "appNumber") != OTHER_APP or field(notice, "appRating") != "14":
        raise ValueError("Unexpected application-level notice target")
    if found.get(OTHER_APP) != ("14", "57000", "true"):
        raise ValueError("Notice target not matched to historical final protocol")
    if field(notice, "protocolNumber") != "1":
        raise ValueError("Notice references other protocol")

    return {
        "procurement_ref": AKSAY,
        "source_zip_sha256": archive_sha,
        "final_xml_sha256": FINAL_XML_SHA,
        "notice_xml_sha256": NOTICE_XML_SHA,
        "final_published_at": final_at.isoformat(),
        "application_notice_published_at": notice_at.isoformat(),
        "notice_document_kind": "epNoticeApplicationCancel",
        "notice_application_number": OTHER_APP,
        "notice_application_rating_from_final": "14",
        "company_application_number": OUR_APP,
        "company_original_final_price_rub": "119000",
        "company_original_final_app_rating": "38",
        "notice_targets_company_application": False,
        "whole_procurement_cancelled_proven_by_notice": False,
        "new_ranking_after_notice_verified": False,
        "training_label_approved": False,
        "new_postgresql_records": 0,
        "mutations": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-eis-zip", type=Path, default=Path(
        "/Volumes/ArvectumSSD/Arvectum/data/tenders/eis/" + AKSAY + "/documentation-archive.zip"
    ))
    args = parser.parse_args(argv)
    print(json.dumps(audit_aksay_postfinal(args.original_eis_zip),
                     indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
