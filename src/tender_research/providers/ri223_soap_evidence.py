"""Bounded, read-only evidence projection from an authentic RI223 getDocsIP ZIP.

Only observed source fields are populated. SOAP delivery state is not a
procurement status, and no 44-FZ procedural assumptions are applied.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlparse
from zipfile import BadZipFile, ZipFile

from src.tender_research.schemas import EisDocumentRaw, EisTenderRaw

RI223_NAMESPACE = "http://zakupki.gov.ru/223fz/purchase/1"
MAX_XML_ENTRIES = 256
MAX_XML_BYTES = 8 * 1024 * 1024
MAX_TOTAL_XML_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024


class Ri223EvidenceError(ValueError):
    """Archive is unsupported, ambiguous, corrupt or source-inconsistent."""


def _local(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _one(node: ET.Element | None, tag: str) -> ET.Element | None:
    if node is None:
        return None
    matches = [child for child in node if _local(child) == tag]
    if len(matches) > 1:
        raise Ri223EvidenceError(f"ambiguous duplicate XML field: {tag}")
    return matches[0] if matches else None


def _text(node: ET.Element | None, tag: str) -> str | None:
    child = _one(node, tag)
    value = (child.text or "").strip() if child is not None else ""
    return value or None


def _children(node: ET.Element | None, tag: str) -> list[ET.Element]:
    return [
        child for child in (node if node is not None else ()) if _local(child) == tag
    ]


def _data_root(root: ET.Element, expected: str, data_tag: str) -> ET.Element:
    if root.tag != f"{{{RI223_NAMESPACE}}}{expected}":
        raise Ri223EvidenceError(f"unsupported RI223 XML root: {_local(root)}")
    data = _one(_one(_one(root, "body"), "item"), data_tag)
    if data is None:
        raise Ri223EvidenceError(f"missing {data_tag} in RI223 XML")
    return data


def _source(archive_hash: str, name: str, xml_hash: str, path: str) -> dict:
    return {
        "regime": "223fz",
        "source": "RI223_getDocsIP",
        "archive_sha256": archive_hash,
        "xml_member": name,
        "xml_sha256": xml_hash,
        "xpath": path,
    }


def _decimal(value: str | None) -> Decimal | None:
    try:
        return (
            Decimal(value) if value is not None and Decimal(value).is_finite() else None
        )
    except InvalidOperation:
        return None


def _date(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


def _parse_lots(
    data: ET.Element, archive_hash: str, member: str, xml_hash: str
) -> list[dict]:
    lots = _one(data, "lots")
    output: list[dict] = []
    for index, lot in enumerate(_children(lots, "lot"), 1):
        info = _one(lot, "lotData")
        if info is None:
            raise Ri223EvidenceError("lot without lotData")
        base = f"/purchaseNotice/body/item/purchaseNoticeData/lots/lot[{index}]"
        positions: list[dict] = []
        for position_index, position in enumerate(
            _children(_one(info, "lotItems"), "lotItem"), 1
        ):
            position_path = f"{base}/lotData/lotItems/lotItem[{position_index}]"
            positions.append(
                {
                    "ordinal_number": _text(position, "ordinalNumber"),
                    "okpd2_code": _text(_one(position, "okpd2"), "code"),
                    "okpd2_name": _text(_one(position, "okpd2"), "name"),
                    "quantity": _text(position, "qty"),
                    "unit_code": _text(_one(position, "okei"), "code"),
                    "unit_name": _text(_one(position, "okei"), "name"),
                    "evidence": _source(archive_hash, member, xml_hash, position_path),
                }
            )
        output.append(
            {
                "ordinal_number": _text(lot, "ordinalNumber"),
                "subject": _text(info, "subject"),
                "initial_sum": _text(info, "initialSum"),
                "currency_code": _text(_one(info, "currency"), "code"),
                "positions": positions,
                "evidence": _source(archive_hash, member, xml_hash, base),
            }
        )
    return output


def _select_observed_notice(
    documents: list[tuple[str, str, ET.Element]],
    registry_number: str,
    archive_hash: str,
) -> tuple[tuple[str, str, ET.Element], list[dict], str]:
    """Select the highest *observed* version only on unambiguous source ordering.

    It is not a determination that the chosen notice is legally effective.
    """
    if not documents:
        raise Ri223EvidenceError("exactly one notice version required; none found")
    candidates = []
    seen_versions: set[str] = set()
    for member, digest, root in documents:
        data = _data_root(root, "purchaseNotice", "purchaseNoticeData")
        if _text(data, "registrationNumber") != registry_number:
            raise Ri223EvidenceError(
                "notice registry number does not match requested number"
            )
        source_version = _text(data, "version")
        if len(documents) > 1 and not (
            source_version and re.fullmatch(r"[1-9]\d{0,5}", source_version)
        ):
            raise Ri223EvidenceError(
                "ambiguous notice version: numeric versions required"
            )
        if len(documents) > 1:
            if source_version in seen_versions:
                raise Ri223EvidenceError(
                    "ambiguous: only one notice version per version code permitted"
                )
            seen_versions.add(source_version)
        published = _date(_text(data, "publicationDateTime"))
        modified = _date(_text(data, "modificationDate"))
        if len(documents) > 1 and (published is None or modified is None):
            raise Ri223EvidenceError("ambiguous notice version chronology")
        candidates.append(
            (
                int(source_version)
                if source_version and source_version.isdecimal()
                else 0,
                published,
                modified,
                member,
                digest,
                root,
                data,
            )
        )
    candidates.sort(key=lambda row: row[0])
    if len(candidates) > 1:
        versions = [row[0] for row in candidates]
        if len(set(versions)) != len(versions):
            raise Ri223EvidenceError("ambiguous duplicate notice version")
        for older, newer in pairwise(candidates):
            try:
                consistent = older[1] < newer[1] and older[2] <= newer[2]
            except TypeError as exc:
                raise Ri223EvidenceError("ambiguous notice version chronology") from exc
            if not consistent:
                raise Ri223EvidenceError("ambiguous notice version chronology")
    history = [
        {
            "source_version": _text(data, "version"),
            "publication_datetime": _text(data, "publicationDateTime"),
            "modification_datetime": _text(data, "modificationDate"),
            "modification_description": _text(data, "modificationDescription"),
            "submission_close_datetime": _text(data, "submissionCloseDateTime"),
            "source_status_code": _text(data, "status"),
            "lot_count": len(_children(_one(data, "lots"), "lot")),
            "evidence": _source(
                archive_hash,
                member,
                digest,
                "/purchaseNotice/body/item/purchaseNoticeData",
            ),
        }
        for _version, _published, _modified, member, digest, _root, data in candidates
    ]
    selected = candidates[-1]
    basis = (
        "HIGHEST_OBSERVED_NUMERIC_VERSION_WITH_CHRONOLOGY"
        if len(candidates) > 1
        else "SINGLE_OBSERVED_NOTICE"
    )
    return (selected[3], selected[4], selected[5]), history, basis


def parse_ri223_archive(archive: Path, registry_number: str) -> EisTenderRaw:
    """Project exact notice, revisions and clarifications as read-only XML evidence.

    An ordered source version is not a legal effective-version conclusion.
    Protocols/clarifications cannot determine award, eligibility or status.
    """
    if not re.fullmatch(r"\d{11}", registry_number):
        raise Ri223EvidenceError("invalid 223-FZ registry number")
    archive = Path(archive)
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise Ri223EvidenceError("compressed RI223 archive too large")
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    notice_docs: list[tuple[str, str, ET.Element]] = []
    protocol_docs: list[tuple[str, str, ET.Element]] = []
    explanation_docs: list[tuple[str, str, ET.Element]] = []
    try:
        with ZipFile(archive) as bundle:
            infos = [
                info
                for info in bundle.infolist()
                if info.filename.lower().endswith(".xml")
            ]
            if len({info.filename for info in infos}) != len(infos):
                raise Ri223EvidenceError("duplicate ZIP member names")
            if len(infos) > MAX_XML_ENTRIES:
                raise Ri223EvidenceError("too many XML documents")
            if sum(info.file_size for info in infos) > MAX_TOTAL_XML_BYTES:
                raise Ri223EvidenceError("RI223 XML archive too large")
            for info in infos:
                if info.file_size > MAX_XML_BYTES:
                    raise Ri223EvidenceError("RI223 XML member too large")
                payload = bundle.read(info)
                if re.search(rb"<!\s*(DOCTYPE|ENTITY)\b", payload, re.IGNORECASE):
                    raise Ri223EvidenceError("DTD/entity definitions not permitted")
                try:
                    root = ET.fromstring(payload)
                except ET.ParseError as exc:
                    raise Ri223EvidenceError("malformed RI223 XML") from exc
                xml_hash = hashlib.sha256(payload).hexdigest()
                if _local(root) == "purchaseNotice":
                    notice_docs.append((info.filename, xml_hash, root))
                elif _local(root) == "purchaseProtocol":
                    protocol_docs.append((info.filename, xml_hash, root))
                elif _local(root) == "explanation":
                    explanation_docs.append((info.filename, xml_hash, root))
                else:
                    raise Ri223EvidenceError(
                        f"unsupported RI223 document: {_local(root)}"
                    )
    except (BadZipFile, OSError, RuntimeError) as exc:
        raise Ri223EvidenceError("unreadable RI223 ZIP archive") from exc

    (notice_name, notice_hash, notice), notice_history, selection_basis = (
        _select_observed_notice(notice_docs, registry_number, archive_hash)
    )
    data = _data_root(notice, "purchaseNotice", "purchaseNoticeData")
    lots = _parse_lots(data, archive_hash, notice_name, notice_hash)
    if not lots:
        raise Ri223EvidenceError("notice has no supported source-bound lots")
    protocols = []
    protocol_document_groups: list[tuple[ET.Element, str, str]] = []
    for protocol_name, protocol_hash, protocol in protocol_docs:
        body = _data_root(protocol, "purchaseProtocol", "purchaseProtocolData")
        info = _one(body, "purchaseInfo")
        notice_number = _text(info, "purchaseNoticeNumber")
        if notice_number != registry_number:
            raise Ri223EvidenceError("protocol not bound to requested notice number")
        protocol_document_groups.append((body, protocol_name, protocol_hash))
        protocols.append(
            {
                "registration_number": _text(body, "registrationNumber"),
                "notice_number": notice_number,
                "type_name": _text(body, "typeName"),
                "source_status_code": _text(body, "status"),
                "source_version": _text(body, "version"),
                "evidence": _source(
                    archive_hash,
                    protocol_name,
                    protocol_hash,
                    "/purchaseProtocol/body/item/purchaseProtocolData",
                ),
            }
        )
    explanations = []
    explanation_document_groups: list[tuple[ET.Element, str, str]] = []
    if len(explanation_docs) > 64:
        raise Ri223EvidenceError("too many RI223 explanations")
    for explanation_name, explanation_hash, explanation in explanation_docs:
        body = _data_root(explanation, "explanation", "explanationData")
        purchase_number = _text(body, "purchaseRegNum")
        if purchase_number != registry_number:
            raise Ri223EvidenceError("explanation not bound to requested notice number")
        raw_question = _text(body, "requestSubjectInfo")
        raw_description = _text(body, "description")
        explanation_document_groups.append((body, explanation_name, explanation_hash))
        explanations.append(
            {
                "notice_number": purchase_number,
                "source_guid": _text(body, "guid"),
                "request_subject_info": raw_question[:4096] if raw_question else None,
                "request_text_truncated": bool(
                    raw_question and len(raw_question) > 4096
                ),
                "source_description": raw_description[:4096]
                if raw_description
                else None,
                "description_truncated": bool(
                    raw_description and len(raw_description) > 4096
                ),
                "request_date": _text(body, "requestDate"),
                "publish_date": _text(body, "publishDate"),
                "source_status_code": _text(body, "status"),
                "source_lot_binding": "UNKNOWN",
                "attachment_count": len(
                    _children(_one(body, "attachments"), "document")
                ),
                "evidence": _source(
                    archive_hash,
                    explanation_name,
                    explanation_hash,
                    "/explanation/body/item/explanationData",
                ),
            }
        )
    # Notice/protocol/explanation references are independent source-bound records;
    # no legacy 44-FZ fallback is permitted to enumerate or fetch them.
    documents: list[EisDocumentRaw] = []
    seen_ids: set[str] = set()
    document_groups = [
        (
            data,
            notice_name,
            notice_hash,
            "/purchaseNotice/body/item/purchaseNoticeData",
        ),
        *[
            (body, name, digest, "/purchaseProtocol/body/item/purchaseProtocolData")
            for body, name, digest in protocol_document_groups
        ],
        *[
            (body, name, digest, "/explanation/body/item/explanationData")
            for body, name, digest in explanation_document_groups
        ],
    ]
    for parent, member, digest, base_path in document_groups:
        for index, entry in enumerate(
            _children(_one(parent, "attachments"), "document"), 1
        ):
            document_id = _text(entry, "contentUid") or _text(entry, "guid")
            file_name = _text(entry, "fileName")
            file_url = _text(entry, "url")
            if not document_id or not file_name or not file_url:
                continue
            parsed_url = urlparse(file_url)
            host = (parsed_url.hostname or "").lower()
            if parsed_url.scheme != "https" or not (
                host == "zakupki.gov.ru" or host.endswith(".zakupki.gov.ru")
            ):
                raise Ri223EvidenceError("unsupported RI223 document URL origin")
            if document_id in seen_ids:
                continue
            seen_ids.add(document_id)
            documents.append(
                EisDocumentRaw(
                    source_document_id=document_id,
                    file_name=file_name,
                    file_url=file_url,
                    raw_meta={
                        "source_regime": "223fz",
                        "source_document_kind": (
                            "explanation"
                            if base_path.startswith("/explanation")
                            else "purchaseProtocol"
                            if base_path.startswith("/purchaseProtocol")
                            else "purchaseNotice"
                        ),
                        "evidence": _source(
                            archive_hash,
                            member,
                            digest,
                            f"{base_path}/attachments/document[{index}]",
                        ),
                    },
                )
            )
    sum_value = _decimal(lots[0]["initial_sum"]) if len(lots) == 1 else None
    if sum_value is not None and (sum_value < 0 or sum_value > Decimal("1e15")):
        sum_value = None
    raw_payload = {
        "source_regime": "223fz",
        "source_subsystem": "RI223",
        "read_only": True,
        "archive_sha256": archive_hash,
        "notice_version": _text(data, "version"),
        "notice_versions": notice_history,
        "notice_selection_basis": selection_basis,
        "notice_effective_status": "UNKNOWN",
        "notice_source_status_code": _text(data, "status"),
        "procurement_status": "UNKNOWN",  # SOAP 'completed' is only transport state.
        "amendment_semantics": "UNKNOWN",
        "clarifications": "OBSERVED" if explanations else "NOT_OBSERVED",
        "explanations": explanations,
        "explanations_observed": bool(explanations),
        "lots": lots,
        "notice_attachment_count": len(
            _children(_one(data, "attachments"), "document")
        ),
        "source_document_reference_count": len(documents),
        "protocols": protocols,
        "protocols_observed": bool(protocols),
        "evidence": _source(
            archive_hash,
            notice_name,
            notice_hash,
            "/purchaseNotice/body/item/purchaseNoticeData",
        ),
    }
    return EisTenderRaw(
        external_id=registry_number,
        registry_number=registry_number,
        law_type="223fz",
        title=_text(data, "name") or f"Закупка {registry_number}",
        publication_date=_date(_text(data, "publicationDateTime")),
        nmck_amount=float(sum_value) if sum_value is not None else None,
        currency=lots[0]["currency_code"] if sum_value is not None else None,
        status=None,
        documents=documents,
        raw_payload=raw_payload,
    )
