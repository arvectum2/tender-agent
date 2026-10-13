"""Source-attested EIS 44-FZ procedure classification from bounded original ZIP/XML.

This is an archive-only gate: never claims live notice validity, eligibility or GO.
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

_COMPETITIVE = {"epNotificationEF2020", "epNotificationEZK2020", "epNotificationEOK2020"}
_SPECIAL = "epNotificationEZT2020"
_NOTICE_NAME = re.compile(r"^(epNotification[A-Za-z0-9]+)_([0-9]{19})_([0-9]+)_[A-Za-z0-9-]+\.xml$")
_MAX_ZIP_BYTES = 8_000_000
_MAX_XML_BYTES = 2_000_000


def classify_official_eis_archive(archive_path: Path, procurement_number: str) -> dict[str, Any]:
    """Classify ONLY authentic document semantics, bound to requested procurement.

    UNKNOWN/CONFLICT must never be interpreted as a competitive procurement.
    The SHA receipts identify actual locally retained archive bytes, not a
    legal digital signature or the latest current EIS notice.
    """
    base: dict[str, Any] = {
        "status": "UNKNOWN",
        "procedure_kind": "UNKNOWN",
        "notice_type": None,
        "archive_sha256": None,
        "notice_xml_sha256": None,
        "source_purchase_number": None,
        "source_version": None,
        "current_live_eis_verified": False,
        "business_go_eligible": False,
    }

    def inconclusive(reason: str, status: str = "UNKNOWN") -> dict[str, Any]:
        return {**base, "status": status, "reason": reason}

    if not re.fullmatch(r"[0-9]{19}", procurement_number):
        return inconclusive("PROCUREMENT_NUMBER_INVALID", "CONFLICT")
    if archive_path.is_symlink() or not archive_path.is_file():
        return inconclusive("OFFICIAL_ARCHIVE_UNAVAILABLE")
    if archive_path.stat().st_size > _MAX_ZIP_BYTES:
        return inconclusive("OFFICIAL_ARCHIVE_OVERSIZED")
    try:
        raw = archive_path.read_bytes()
        if not zipfile.is_zipfile(archive_path):
            return inconclusive("OFFICIAL_ARCHIVE_INVALID")
        digest = hashlib.sha256(raw).hexdigest()
        notices: list[tuple[int, str, str]] = []
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            if len(infos) > 250:
                return inconclusive("ARCHIVE_MEMBER_LIMIT")
            for info in infos:
                name = Path(info.filename).name
                if not name.startswith("epNotification") or not name.endswith(".xml"):
                    continue
                match = _NOTICE_NAME.fullmatch(name)
                if (not match or Path(info.filename).name != info.filename
                    or info.file_size > _MAX_XML_BYTES or info.flag_bits & 0x1):
                    return inconclusive("OFFICIAL_NOTICE_XML_INVALID")
                declared_type, number, version = match.groups()
                if number != procurement_number:
                    return inconclusive("OFFICIAL_NOTICE_NUMBER_CONFLICT", "CONFLICT")
                payload = archive.read(info)
                if len(payload) > _MAX_XML_BYTES:
                    return inconclusive("OFFICIAL_NOTICE_XML_OVERSIZED")
                element = ET.fromstring(payload)
                if element.tag.rsplit("}", 1)[-1] != "export":
                    return inconclusive("OFFICIAL_NOTICE_XML_STRUCTURE_UNKNOWN")
                elements = list(element)
                if len(elements) != 1 or elements[0].tag.rsplit("}", 1)[-1] != declared_type:
                    return inconclusive("OFFICIAL_NOTICE_TYPE_CONFLICT", "CONFLICT")
                # EIS also uses purchaseNumber in unrelated nested service
                # fields. The authoritative 19-digit registry number is the
                # direct child of the notice's direct commonInfo section.
                common_infos = [
                    x for x in elements[0]
                    if x.tag.rsplit("}", 1)[-1] == "commonInfo"
                ]
                recorded = [
                    (x.text or "").strip() for section in common_infos
                    for x in section
                    if x.tag.rsplit("}", 1)[-1] == "purchaseNumber"
                ]
                if len(common_infos) != 1 or recorded != [procurement_number]:
                    return inconclusive("OFFICIAL_NOTICE_PURCHASE_NUMBER_CONFLICT", "CONFLICT")
                notices.append((int(version), declared_type, hashlib.sha256(payload).hexdigest()))
        if not notices:
            return inconclusive("OFFICIAL_NOTICE_XML_MISSING")
        types = {x[1] for x in notices}
        if len(types) != 1:
            return inconclusive("OFFICIAL_NOTICE_MIXED_PROCEDURES", "CONFLICT")
        version, document_type, notice_sha = max(notices)
        if document_type == _SPECIAL:
            kind = "SINGLE_SUPPLIER_ART93_12"
            state = "ATTESTED_SPECIAL"
        elif document_type in _COMPETITIVE:
            kind = "COMPETITIVE_44FZ"
            state = "ATTESTED_COMPETITIVE"
        else:
            kind = "UNKNOWN"
            state = "UNKNOWN"
        return {
            **base, "status": state, "procedure_kind": kind,
            "notice_type": document_type, "archive_sha256": digest,
            "notice_xml_sha256": notice_sha, "source_purchase_number": procurement_number,
            "source_version": version, "reason": "ARCHIVED_XML_TYPE_ONLY_NOT_LIVE_LEGAL_STATUS",
        }
    except (OSError, zipfile.BadZipFile, RuntimeError, ET.ParseError, ValueError):
        return inconclusive("OFFICIAL_NOTICE_PARSING_FAILED")
