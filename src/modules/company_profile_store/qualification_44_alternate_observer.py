"""Read-only original EOK2020 PDF criterion observation, never a supplier NO_GO.

A different 44-FZ competition can allocate only a tiny part of its 40%
qualification section to completed contracts; never reuse CZN's 70/30 gate.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from src.modules.company_profile_store.qualification_original_source import (
    OriginalScoringEvidence,
    _first,
    _local_name,
    _original_current_notice,
)

_MAX_PDF_BYTES = 8 * 1024 * 1024


def _single_pct(text: str, pattern: str, label: str) -> int:
    matches = re.findall(pattern, text, flags=re.MULTILINE | re.IGNORECASE)
    if len(matches) != 1 or not matches[0].isdigit():
        raise ValueError(f"Original scoring weight absent/ambiguous: {label}")
    pct = int(matches[0])
    if not 0 <= pct <= 100:
        raise ValueError(f"Invalid scoring weight: {label}")
    return pct


def observe_44_alternate_pdf_text(text: str) -> dict:
    """Extract narrow source layout; no specialist/document qualification scoring."""
    if (
        len(text) > 1_000_000
        or "ПОРЯДОК" not in text.upper()
        or "рассмотрения и оценки заявок" not in text.lower()
    ):
        raise ValueError("Not an observed original EOK2020 evaluation PDF")
    price = _single_pct(
        text, r"^1\.\s+Цена\s+контракта,\s+([0-9]{1,3})\b", "price"
    )
    qualification = _single_pct(
        text, r"^4\.\s+Квалификация\s+([0-9]{1,3})\b", "qualification"
    )
    contracts = _single_pct(
        text, r"^\s+контракта\s+([0-9]{1,3})\s+характеристика", "contracts"
    )
    specialists = _single_pct(
        text, r"^\s+наличие\s+у\s+([0-9]{1,3})\s+характеристика", "specialists"
    )
    if price + qualification != 100 or contracts + specialists != 100:
        raise ValueError("Original composite scoring percentages inconsistent")
    if not re.search(r"количество\s+исполненных\s+контрактов", text, re.IGNORECASE):
        raise ValueError("Cannot relate 5% row to completed contracts")
    if not re.search(r"перечень\s+специалистов\s+и\s+иных\s+работников", text, re.IGNORECASE):
        raise ValueError("Cannot relate 95% row to specialists")
    return {
        "criterion_model": "EOK2020_COMPOSITE_QUALIFICATION",
        "price_weight_percent": price,
        "qualification_weight_percent": qualification,
        "qualification_subweights_percent": {
            "completed_contract_count": contracts,
            "specialists": specialists,
        },
        "completed_contracts_full_score_percent": None,
        "supplier_specialists_confirmed": False,
        "owner_contract_reference_count_used": False,
        "commercial_recommendation": "NOT_ASSESSED",
        "legal_eligibility_assessed": False,
        "human_gold": False,
        "external_action_allowed": False,
        "reason": "Price, contract experience and specialist scores are separate; missing contracts alone does not prove competitive NO_GO.",
    }


def verify_44_alternate_originals(
    *, soap_archive_bytes: bytes, scoring_pdf_bytes: bytes, receipt: dict
) -> dict:
    """Bind official current EIS v2 notice UID to SHA-pinned source PDF."""
    if not scoring_pdf_bytes.startswith(b"%PDF-") or len(scoring_pdf_bytes) > _MAX_PDF_BYTES:
        raise ValueError("Unsupported evaluation document type or byte size")
    if hashlib.sha256(scoring_pdf_bytes).hexdigest() != receipt["scoring_document_sha256"]:
        raise ValueError("Original EIS scoring PDF SHA-256 mismatch")
    if len(scoring_pdf_bytes) != receipt["scoring_document_size_bytes"]:
        raise ValueError("Original EIS scoring PDF size mismatch")
    original_receipt = OriginalScoringEvidence(
        schema_version="eis-original-scoring-receipt-v1",
        procurement_number=receipt["procurement_number"],
        procurement_law=receipt["procurement_law"],
        notice_version=receipt["procurement_notice_version"],
        original_soap_archive_sha256=receipt["original_soap_archive_sha256"],
        original_notice_xml_sha256=receipt["original_notice_xml_sha256"],
        scoring_document_uid=receipt["scoring_document_uid"],
        scoring_document_sha256=receipt["scoring_document_sha256"],
    )
    notice, original_xml_sha = _original_current_notice(
        soap_archive_bytes, original_receipt
    )
    matches = []
    for attachment in notice.iter():
        if _local_name(attachment.tag) != "attachmentInfo":
            continue
        if _first(attachment, "publishedContentId") == receipt["scoring_document_uid"]:
            matches.append(attachment)
    if len(matches) != 1:
        raise ValueError("Scoring PDF UID not unique in current original EIS notice")
    doc = matches[0]
    name = _first(doc, "fileName")
    size = _first(doc, "fileSize")
    source_url = _first(doc, "url")
    url = urlsplit(source_url or "")
    if (
        name != receipt["scoring_document_name"]
        or size != str(len(scoring_pdf_bytes))
        or url.scheme != "https"
        or url.hostname != "zakupki.gov.ru"
        or url.port is not None
        or url.path != "/44fz/filestore/public/1.0/download/priz/file.html"
        or parse_qs(url.query) != {"uid": [receipt["scoring_document_uid"]]}
    ):
        raise ValueError("Original evaluation PDF name/size/HTTPS source mismatch")
    end_dt = _first(notice, "endDT")
    if end_dt != receipt["original_application_deadline"]:
        raise ValueError("Latest original EIS application deadline differs from receipt")
    end = datetime.fromisoformat(end_dt)
    if end.utcoffset() != timedelta(hours=3):
        raise ValueError("Deadline must be verified in Moscow time")
    return {
        "procurement_number": original_receipt.procurement_number,
        "procurement_law": "44fz",
        "notice_version": original_receipt.notice_version,
        "application_deadline": end.isoformat(),
        "scoring_document_uid": receipt["scoring_document_uid"],
        "original_soap_archive_sha256": hashlib.sha256(soap_archive_bytes).hexdigest(),
        "latest_notice_xml_sha256": original_xml_sha,
        "scoring_document_sha256": hashlib.sha256(scoring_pdf_bytes).hexdigest(),
        "source_status": "ORIGINAL_EIS_BYTES_CORRELATED_SIGNATURE_NOT_VERIFIED",
        "digital_signature_validated": False,
    }
