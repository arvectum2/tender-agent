"""Source-bound RD223 public contract records: contractCutted hides suppliers.

A registered total price is never inferred to be PQ equipment turnover.
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def _local(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _get(parent: ET.Element | None, path: str) -> str | None:
    for key in path.split("/"):
        parent = next((x for x in parent if _local(x) == key), None) if parent is not None else None
    text = (parent.text or "").strip() if parent is not None else ""
    return text or None


def extract_public_rd223_registry(
    archive_path: Path, *, archive_sha256: str,
) -> list[dict[str, object]]:
    """Validate original bytes and list revisions without inventing supplier IDs."""
    if not re.fullmatch(r"[0-9a-f]{64}", archive_sha256):
        raise ValueError("Invalid source SHA-256")
    if archive_path.is_symlink() or archive_path.stat().st_size > 200 * 1024 * 1024:
        raise ValueError("Forbidden public registry archive")
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != archive_sha256:
        raise ValueError("Official archive SHA-256 differs")
    rows = []
    with zipfile.ZipFile(archive_path) as bundle:
        members = bundle.infolist()
        if len(members) > 12000 or sum(m.file_size for m in members) > 500 * 1024 * 1024:
            raise ValueError("Registry ZIP exceeds limits")
        seen: set[str] = set()
        for m in members:
            if m.is_dir() or not m.filename.lower().endswith(".xml"):
                continue
            if m.filename.startswith("/") or ".." in Path(m.filename).parts:
                raise ValueError("Unsafe ZIP XML member")
            if m.file_size > 40 * 1024 * 1024:
                raise ValueError("XML exceeds size limits")
            raw = bundle.read(m)
            if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                raise ValueError("XML DTD/entities forbidden")
            checksum = hashlib.sha256(raw).hexdigest()
            if checksum in seen:
                continue
            seen.add(checksum)
            root = ET.fromstring(raw)
            if _local(root) != "contractCutted":
                continue
            item = root
            for key in ("body", "item", "contractData"):
                item = next((x for x in item if _local(x) == key), None) if item is not None else None
            number = _get(item, "contractRegNumber")
            if not number or not re.fullmatch(r"[0-9]{17,32}", number):
                continue
            amount = _get(item, "price")
            if amount is not None and not re.fullmatch(r"[0-9]{1,18}(?:\.[0-9]{1,6})?", amount):
                raise ValueError("Invalid official contract price")
            buyer = _get(item, "customer/mainInfo/inn")
            if buyer and not re.fullmatch(r"[0-9]{10}|[0-9]{12}", buyer):
                buyer = None
            purchase = _get(item, "purchaseNoticeInfo/purchaseNoticeNumber")
            if purchase and not re.fullmatch(r"[0-9]{9,30}", purchase):
                raise ValueError("Invalid procurement number")
            rows.append({
                "registry_number": number,
                "registered_revision_number": _get(item, "registrationNumber"),
                "revision": _get(item, "version"),
                "contract_number": _get(item, "name"),
                "contract_date": _get(item, "contractDate"),
                "linked_procurement": purchase,
                "registered_total_price_rub": amount,
                "buyer_inn": buyer,
                "buyer_name": _get(item, "customer/mainInfo/fullName"),
                "subject": _get(item, "subjectContract"),
                "end_execution_date": _get(item, "endExecutionDate"),
                "modification_description": _get(item, "modificationDescription"),
                "verified_public_contract_registry": True,
                "supplier_inn": None,
                "supplier_identity_from_registry_verified": False,
                "pq_equipment_sale_rub": None,
                "equipment_price_verified": False,
                "amount_paid_verified": False,
                "document_type": "contractCutted",
                "proof": {"archive_sha256": archive_sha256, "xml_member": m.filename, "xml_sha256": checksum},
            })
    return sorted(rows, key=lambda x: (str(x["registry_number"]), str(x["revision"] or "")))
