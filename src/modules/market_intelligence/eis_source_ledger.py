"""Source-bound EIS ZIP XML notice/protocol provenance and conservative linkage.

Data is *candidate evidence*. Protocol bids, ratings and signed-status flags are
NOT certified contract awards or paid contract values. No outside HTML fetching.
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

MAX_ARCHIVE_BYTES = 200 * 1024 * 1024
MAX_MEMBER_BYTES = 40 * 1024 * 1024
MAX_XML_TOTAL = 500 * 1024 * 1024
MAX_XML_MEMBERS = 10000
MAX_APPLICATIONS_PER_PROTOCOL = 2000  # A real 44-FZ EIS protocol has 960 offers; hard bounded.


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _named_children(node: ET.Element, key: str) -> list[ET.Element]:
    return [child for child in node if _local(child.tag) == key]


def _first(node: ET.Element, path: str) -> ET.Element | None:
    current: ET.Element | None = node
    for field in path.split("/"):
        if current is None:
            return None
        current = next((child for child in current if _local(child.tag) == field), None)
    return current


def _text(node: ET.Element, path: str) -> str | None:
    found = _first(node, path)
    result = (found.text or "").strip() if found is not None else ""
    return result or None


def _clean_number(number: str | None) -> str | None:
    if number is None:
        return None
    number = number.strip()
    return number if re.fullmatch(r"[0-9]{9,30}", number) else None


def _literal_bool(value: str | None) -> bool | None:
    if value in ("true", "1"):
        return True
    if value in ("false", "0"):
        return False
    return None


def _safe_decimal(value: str | None) -> str | None:
    # Numeric text evidence only: no currency conversion or price inference.
    return value if value is not None and re.fullmatch(r"[0-9]{1,18}(?:\.[0-9]{1,6})?", value) else None


def _applications(protocol: ET.Element) -> list[dict[str, Any]]:
    rows = []
    # Approved original 223-FZ variants share lotApplicationsList shape
    # but carry a document-type-specific *Data wrapper.
    data = _first(
        protocol, f"body/item/{_local(protocol.tag)}Data/lotApplicationsList",
    )
    if data is None:
        return rows
    for lots in _named_children(data, "protocolLotApplications"):
        ordinal = _text(lots, "lot/ordinalNumber")
        for app in _named_children(lots, "application"):
            if len(rows) >= MAX_APPLICATIONS_PER_PROTOCOL:
                raise ValueError("Protocol application count exceeds safe limit")
            # Original EIS 223-FZ purchaseProtocol uses supplierInfo for the
            # applicant legal entity (provider may be a BOOLEAN marker, not
            # a supplier object). Record that identity as bid evidence only.
            inn = (
                _text(app, "supplierInfo/inn")
                or _text(app, "provider/mainInfo/inn")
                or _text(app, "provider/inn")
            )
            if inn is not None and not re.fullmatch(r"[0-9]{10}|[0-9]{12}", inn):
                inn = None
            provider_name = (
                _text(app, "supplierInfo/name")
                or _text(app, "provider/mainInfo/fullName")
            )
            if provider_name is not None:
                provider_name = provider_name[:300]
            provider_ogrn = _text(app, "supplierInfo/ogrn")
            if provider_ogrn is not None and not re.fullmatch(r"[0-9]{13}|[0-9]{15}", provider_ogrn):
                provider_ogrn = None
            rows.append({
                "lot_ordinal": ordinal,
                "application_number": _text(app, "applicationNumber"),
                "bid_price_text": _safe_decimal(_text(app, "price")),
                "currency_code": _text(app, "currency/code"),
                "provider_inn_evidence": inn,
                "provider_name_evidence": provider_name,
                "provider_ogrn_evidence": provider_ogrn,
                "accepted_raw": _text(app, "accepted"),
                "consideration_accepted_raw": _text(app, "considerationResultInfo/accepted"),
                "winner_indication_raw": _text(app, "winnerIndication"),
                "commission_decision_place_raw": _text(app, "commissionDecisionPlace"),
                "assessment_result_raw": _text(app, "assessmentResult"),
                "accepted_flag": _literal_bool(_text(app, "accepted")),
                "consideration_accepted_flag": _literal_bool(_text(app, "considerationResultInfo/accepted")),
                "contract_signed_flag_unverified": _literal_bool(_text(app, "contractSigned")),
                "rating_raw": _text(app, "rating"),
                "winner_verified": False,
                "signed_contract_price_verified": False,
            })
    return rows


def _applications_44(root: ET.Element) -> list[dict[str, Any]]:
    kind = _local(root.tag)
    if kind == "epProtocolEF2020Final":
        holder = _first(root, "protocolInfo/applicationsInfo")
        nodes = _named_children(holder, "applicationInfo") if holder is not None else []
        rows = []
        for app in nodes:
            if len(rows) >= MAX_APPLICATIONS_PER_PROTOCOL:
                raise ValueError("44-FZ protocol applications exceed bound")
            rows.append({
                "application_number": _text(app, "commonInfo/appNumber"),
                "bid_price_text": _safe_decimal(_text(app, "finalPrice") or _text(app, "lastPriceOffer/price")),
                "rating_raw": None,
                "winner_verified": False,
                "signed_contract_price_verified": False,
            })
        return rows
    holder = _first(root, "applications")
    nodes = _named_children(holder, "application") if holder is not None else []
    rows = []
    for app in nodes:
        if len(rows) >= MAX_APPLICATIONS_PER_PROTOCOL:
            raise ValueError("44-FZ legacy applications exceed bound")
        rows.append({
            "application_number": _text(app, "journalNumber") or _text(app, "appNumber"),
            "bid_price_text": _safe_decimal(_text(app, "price")),
            "rating_raw": None,
            "winner_verified": False,
            "signed_contract_price_verified": False,
        })
    return rows


def _document_fields(root: ET.Element) -> dict[str, Any]:
    kind = _local(root.tag)
    if kind in ("purchaseNotice", "purchaseNoticeZKESMBO", "purchaseNoticeZPESMBO", "purchaseNoticeKESMBO"):
        original = _first(root, f"body/item/{kind}Data")
        if original is None:
            return {
                "record_kind": "notice", "notice_number": None,
                "protocol_number": None, "applications": [],
                "customer_company_name": None, "customer_inn_evidence": None,
                "initial_lots": [],
            }
        number = _clean_number(_text(original, "registrationNumber"))
        customer_name = _text(original, "customer/mainInfo/fullName")
        if customer_name:
            customer_name = customer_name[:300]
        customer_inn = _text(original, "customer/mainInfo/inn")
        if customer_inn is not None and not re.fullmatch(r"[0-9]{10}|[0-9]{12}", customer_inn):
            customer_inn = None
        lots_node = _first(original, "lots")
        original_lots = _named_children(lots_node, "lot") if lots_node is not None else []
        if len(original_lots) > 500:
            raise ValueError("Official notice lot count exceeds safe limit")
        lots = []
        for lot in original_lots:
            # Original lotData/initialSum is a declared initial price, NOT
            # actual winner bid, contract price or equipment turnover.
            lots.append({
                "lot_ordinal": _text(lot, "ordinalNumber"),
                "subject_excerpt": (_text(lot, "lotData/subject") or "")[:300],
                "initial_sum_text": _safe_decimal(_text(lot, "lotData/initialSum")),
                "currency_code": _text(lot, "lotData/currency/code"),
                "price_kind": "source_initial_lot_sum_not_contract",
                "winner_verified": False,
            })
        return {
            "record_kind": "notice",
            "notice_number": number,
            "protocol_number": None,
            "applications": [],
            "customer_company_name": customer_name,
            "customer_inn_evidence": customer_inn,
            "initial_lots": lots,
        }
    if kind in (
        "purchaseProtocol", "purchaseProtocolSummingupZKESMBO",
        "purchaseProtocolRZ1ZPESMBO", "purchaseProtocolRZ2ZPESMBO",
        "purchaseProtocolSummingupZPESMBO", "purchaseProtocolSummingupKESMBO",
    ):
        original = _first(root, f"body/item/{kind}Data")
        return {
            "record_kind": "protocol",
            "notice_number": _clean_number(_text(original, "purchaseInfo/purchaseNoticeNumber")) if original is not None else None,
            "protocol_number": _text(original, "registrationNumber") if original is not None else None,
            "applications": _applications(root),
            "winner_verified": False,
            "signed_contract_price_verified": False,
        }
    if kind in ("epProtocolEF2020Final", "fcsPlacementResult", "fcsProposalsResult"):
        number = _clean_number(
            _text(root, "commonInfo/purchaseNumber")
            if kind == "epProtocolEF2020Final"
            else _text(root, "purchaseNumber")
        )
        protocol_number = (
            _text(root, "commonInfo/docNumber") if kind == "epProtocolEF2020Final"
            else (_text(root, "foundationProtocolNumber") or _text(root, "protocolNumber"))
        )
        return {
            "record_kind": "protocol",
            "notice_number": number,
            "protocol_number": protocol_number,
            "applications": _applications_44(root),
        }
    if kind.startswith("epNotification"):
        # Actual 44-FZ document trees vary; never guess which generic number
        # is a procurement ID. If the designated field is absent, leave null.
        number = _clean_number(
            _text(root, "purchaseNumber")
            or _text(root, "body/item/purchaseNumber")
            or _text(root, "commonInfo/purchaseNumber")
        )
        return {
            "record_kind": "notice",
            "notice_number": number,
            "protocol_number": None,
            "applications": [],
        }
    return {
        "record_kind": "other_primary_xml",
        "notice_number": None,
        "protocol_number": None,
        "applications": [],
    }


def extract_archive(
    zip_path: Path, *, official_archive_sha256: str,
    subsystem: str, region: str, exact_date: str,
) -> list[dict[str, Any]]:
    """Return source-sha-qualified original XML records without extracting ZIP."""
    if subsystem not in ("RI223", "PRIZ") or not re.fullmatch(r"[0-9]{2}", region):
        raise ValueError("Invalid official source selector")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", exact_date):
        raise ValueError("Invalid official source date")
    if zip_path.is_symlink() or zip_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Forbidden archive path or ZIP size")
    if not re.fullmatch(r"[0-9a-f]{64}", official_archive_sha256):
        raise ValueError("Invalid source digest")
    archive = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    if archive != official_archive_sha256:
        raise ValueError("Primary ZIP SHA-256 differs from official receipt")
    output = []
    seen = set()
    with zipfile.ZipFile(zip_path) as bundle:
        members = bundle.infolist()
        if len(members) > MAX_XML_MEMBERS:
            raise ValueError("ZIP member count exceeds limit")
        if sum(m.file_size for m in members) > MAX_XML_TOTAL:
            raise ValueError("ZIP uncompressed bytes exceed limit")
        for member in members:
            if not member.filename.lower().endswith(".xml") or member.is_dir():
                continue
            if (member.filename.startswith("/")
                    or ".." in Path(member.filename).parts):
                raise ValueError("Unsafe ZIP member name")
            if member.file_size > MAX_MEMBER_BYTES:
                raise ValueError("XML byte limit exceeded")
            data = bundle.read(member)
            if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                raise ValueError("XML DTD/entities forbidden")
            xml_sha = hashlib.sha256(data).hexdigest()
            if xml_sha in seen:
                continue
            seen.add(xml_sha)
            root = ET.fromstring(data)
            document_root = root
            if _local(root.tag) == "export":
                # The actual EIS 44-FZ download format wraps epNotification
                # in <export>. Never guess when multiple document children exist.
                payload = [
                    child for child in root
                    if _local(child.tag).startswith("epNotification")
                    or _local(child.tag) in (
                        "epProtocolEF2020Final", "fcsPlacementResult", "fcsProposalsResult"
                    )
                ]
                if len(payload) == 1:
                    document_root = payload[0]
            fields = _document_fields(document_root)
            output.append({
                "schema_version": "eis-primary-source-xml/0.1",
                "subsystem": subsystem, "region": region,
                "exact_date": exact_date,
                "xml_root": _local(document_root.tag),
                "transport_root": _local(root.tag),
                **fields,
                "source": {
                    "official_archive_sha256": official_archive_sha256,
                    "xml_member": member.filename,
                    "xml_sha256": xml_sha,
                    "integrity": "verified_sha256",
                },
                "classification": "official_xml_requires_evidence_review",
                "winner_verified": False,
                "signed_contract_price_verified": False,
            })
    return output


def link_original_documents(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Group original notices/protocols by exact registry number; never pick winner."""
    pairs: dict[str, dict[str, Any]] = {}
    unknown = 0
    for row in records:
        number = row.get("notice_number")
        if number is None:
            unknown += 1
            continue
        group = pairs.setdefault(number, {"notice_number": number, "notices": [], "protocols": []})
        if row["record_kind"] == "notice":
            group["notices"].append(row["source"])
        elif row["record_kind"] == "protocol":
            group["protocols"].append({
                "source": row["source"],
                "protocol_number": row["protocol_number"],
                "applications_count": len(row.get("applications", [])),
                "winner_verified": False,
            })
    for group in pairs.values():
        for key in ("notices", "protocols"):
            unique = {item["xml_sha256"] if key == "notices" else item["source"]["xml_sha256"]: item for item in group[key]}
            group[key] = [unique[k] for k in sorted(unique)]
    return {
        "schema_version": "eis-notice-protocol-linkage/0.1",
        "source_records_inspected": len(records),
        "unlinked_missing_notice_number": unknown,
        "joined_by_exact_notice_number": True,
        "winner_verified": False,
        "contract_price_verified": False,
        "groups": [pairs[number] for number in sorted(pairs)],
    }
