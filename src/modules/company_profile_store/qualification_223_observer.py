"""Bounded, source-bound observation of a REAL composite RI223 scoring methodology.

This deliberately does not convert "60% nonprice" into "60% past contracts",
does not compute a supplier GO/NO_GO and does not validate EIS signatures.
"""
from __future__ import annotations

import hashlib
import io
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

_READ_LIMIT = 8 * 1024 * 1024


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _one(parent: ET.Element, tag: str) -> str:
    values = [
        (e.text or "").strip()
        for e in parent.iter()
        if e.tag.rsplit("}", 1)[-1] == tag and e.text and e.text.strip()
    ]
    if len(values) != 1:
        raise ValueError(f"Missing or ambiguous original RI223 field {tag}")
    return values[0]


def verify_ri223_originals(
    soap_archive_bytes: bytes,
    rar_archive_bytes: bytes,
    pdf_bytes: bytes,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Verify original archived source relationship, not a detached signature."""
    for content, field in (
        (soap_archive_bytes, "soap_original_sha256"),
        (rar_archive_bytes, "original_attachment_sha256"),
        (pdf_bytes, "evaluation_pdf_sha256"),
    ):
        if not content or len(content) > _READ_LIMIT or _sha(content) != receipt[field]:
            raise ValueError(f"Original RI223 source checksum mismatch: {field}")

    if receipt.get("law") != "223fz" or not re.fullmatch(
        r"[0-9]{11}", str(receipt.get("procurement_number", ""))
    ):
        raise ValueError("Unsupported original RI223 registry number/law")

    if b"<!DOCTYPE" in soap_archive_bytes.upper() or b"<!ENTITY" in soap_archive_bytes.upper():
        raise ValueError("Unsafe original SOAP bytes")

    with zipfile.ZipFile(io.BytesIO(soap_archive_bytes)) as archive:
        names = archive.namelist()
        if len(names) != 1 or names[0] != receipt["soap_notice_member"]:
            raise ValueError("Unexpected original RI223 notice archive member")
        info = archive.getinfo(names[0])
        if info.file_size > _READ_LIMIT:
            raise ValueError("Oversized original RI223 XML")
        raw = archive.read(info)
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Unsafe original RI223 XML")
    root = ET.fromstring(raw)
    if root.tag.rsplit("}", 1)[-1] != "purchaseNotice":
        raise ValueError("Original RI223 XML is not purchaseNotice")
    if _one(root, "registrationNumber") != receipt["procurement_number"]:
        raise ValueError("Original RI223 registry number mismatch")
    if int(_one(root, "version")) != receipt["soap_notice_version"]:
        raise ValueError("Original RI223 notice version mismatch")

    matches = []
    for document in root.iter():
        if document.tag.rsplit("}", 1)[-1] != "document":
            continue
        fields = {}
        for key in ("fileName", "contentUid", "url"):
            try:
                fields[key] = _one(document, key)
            except ValueError:
                continue
        if fields.get("contentUid") == receipt["original_attachment_content_uid"]:
            matches.append(fields)
    if len(matches) != 1 or matches[0] != {
        "fileName": receipt["original_attachment_name"],
        "contentUid": receipt["original_attachment_content_uid"],
        "url": receipt["original_attachment_url"],
    }:
        raise ValueError("Original RI223 scoring RAR attachment UID/name/official URL mismatch")
    if not receipt["original_attachment_url"].startswith(
        "https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid="
    ):
        raise ValueError("Untrusted RI223 attachment URL")
    return {
        "law": "223fz",
        "procurement_number": receipt["procurement_number"],
        "notice_version": receipt["soap_notice_version"],
        "source_archive_sha256": _sha(soap_archive_bytes),
        "original_rar_sha256": _sha(rar_archive_bytes),
        "original_pdf_sha256": _sha(pdf_bytes),
        "source_status": "ORIGINAL_BYTES_CORRELATED_SIGNATURE_NOT_VERIFIED",
    }


def _percent_row(text: str, label: str, *, index: str) -> int:
    pattern = rf"(?m)^\s*{re.escape(index)}\s+{label}\s+([0-9]{{1,3}})\s*%"
    matches = re.findall(pattern, text, flags=re.IGNORECASE)
    if len(matches) != 1:
        raise ValueError(f"Missing or ambiguous scoring row {index}")
    value = int(matches[0])
    if not 0 <= value <= 100:
        raise ValueError("Invalid original scoring percentage")
    return value


def observe_ri223_scoring_text(text: str) -> dict[str, Any]:
    """Extract only exact visible composite weights, with no bidder judgement."""
    if len(text) > 1_000_000 or "РАЗДЕЛ 9. МЕТОДИКА ОЦЕНКИ" not in text.upper():
        raise ValueError("RI223 source does not clearly contain methodology")
    price = _percent_row(text, "Стоимостной\\s+критерий", index="1")
    nonprice = _percent_row(text, "Нестоимостные\\s+критерии", index="2")
    reputation = _percent_row(text, "Деловая\\s+репутация", index="2.1")
    finances = _percent_row(text, "Финансовое\\s+состояние", index="2.2")
    qualification = _percent_row(text, "Квалификация", index="2.3")
    if price + nonprice != 100 or reputation + finances + qualification != 100:
        raise ValueError("Original RI223 scoring weights inconsistent")
    # Wording is explicitly conditional, so no fixed effective qualification
    # contribution or scoring of completed contracts may be deduced here.
    if not re.search(r"допускается\s+установление", text, re.IGNORECASE):
        raise ValueError("Missing qualification that nonprice split is discretionary")
    return {
        "criterion_model": "RI223_COMPOSITE_NONPRICE_CONDITIONAL",
        "price_weight_percent": price,
        "nonprice_weight_percent": nonprice,
        "candidate_nonprice_subweights": {
            "business_reputation": reputation,
            "financial_condition": finances,
            "qualification": qualification,
        },
        "subweight_binding": "CONDITIONAL_FORMULAR_NOT_CONFIRMED_LOT_APPLIED",
        "supplier_qualification_total_weight_percent": None,
        "completed_contracts_weight_percent": None,
        "lawful_eligibility": "NOT_ASSESSED",
        "competitive_recommendation": "NOT_ASSESSED",
        "required_next_step": "HUMAN_REVIEW_COMPOSITE_CRITERIA_AND_APPLIED_FORMULA",
        "human_gold": False,
        "external_action_allowed": False,
    }
