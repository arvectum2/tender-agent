"""Automatic, read-only qualification of an authenticated supplier's real EIS run.

No user-supplied criterion/UID/checksum/customer_id. The original XML+document
must both come from a saved official getDocsIP run, not manual uploads.
Source confidence is TRANSPORT_CORRELATED, NOT digital-signature verified.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from sqlalchemy.orm import Session

from src.modules.company_profile_store.qualification_original_source import (
    OriginalScoringEvidence,
    _docx_rows,
    _first,
    _local_name,
    _safe_zip,
    _score_table,
    _contract_rules,
    _xml,
    extract_official_qualification_criterion,
)
from src.modules.company_profile_store.qualification_references import (
    assess_company_qualification,
)
from src.modules.tender_operator_agent_demo.upload_service import (
    get_demo_run_input_dir,
    load_demo_run_metadata,
)

_RUN_ID = re.compile(r"toa-run-[0-9]{14}-[a-f0-9]{6}\Z")
_NOTICE_NO = re.compile(r"[0-9]{19}\Z")
_EIS_HOST = "int.zakupki.gov.ru"
_DOCUMENT_HOST = "zakupki.gov.ru"
_ALLOWED_TYPES = {"notice_xml_attachments", "public_notice_documents"}
_MAX_FILE = 10 * 1024 * 1024


def _regular_inside(folder: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not relative:
        raise ValueError("Unsafe original run file name")
    candidate = folder / path
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError("Original run file is missing or a symlink")
    if not candidate.resolve().is_relative_to(folder.resolve()):
        raise ValueError("Original run file escapes the tenant run directory")
    return candidate


def _current_notice_from_archive(archive_bytes: bytes, number: str):
    versions = {}
    with _safe_zip(archive_bytes, xml_archive=True) as archive:
        for member in archive.infolist():
            raw = archive.read(member)
            root = _xml(raw)
            notices = [x for x in root if _local_name(x.tag).startswith("epNotification")]
            if len(notices) > 1:
                raise ValueError("Ambiguous original EIS notice XML")
            if not notices:
                continue
            notice = notices[0]
            version_text = _first(notice, "versionNumber")
            if _first(notice, "purchaseNumber") != number or not version_text or not version_text.isdecimal():
                raise ValueError("Original notice identifier invalid")
            version = int(version_text)
            if version < 1 or version in versions:
                raise ValueError("Duplicate or invalid EIS notice edition")
            versions[version] = (notice, hashlib.sha256(raw).hexdigest())
    if not versions:
        raise ValueError("Official original EIS notice missing")
    return max(versions), versions[max(versions)]


def _archive_bytes(folder: Path) -> bytes:
    candidates = []
    for path in sorted(folder.glob("*.zip"))[:16]:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(folder.resolve()):
            continue
        if path.stat().st_size > 16 * 1024 * 1024:
            continue
        raw = path.read_bytes()
        try:
            with _safe_zip(raw, xml_archive=True) as archive:
                names = [m.filename for m in archive.infolist()]
                if any("epNotification" in x for x in names):
                    candidates.append(raw)
        except (ValueError, OSError, EOFError, KeyError):
            continue
    if len(candidates) != 1:
        raise ValueError("Unique saved original SOAP notice archive not found")
    return candidates[0]


def discover_run_criterion(run_id: str, *, analysis_date: date):
    """Derive one unambiguous assessment from the actual official run files."""
    if not _RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid EIS run identifier")
    metadata = load_demo_run_metadata(run_id)
    number = str(metadata.get("reestr_number") or "").strip()
    if (
        metadata.get("procurement_source") != "zakupki_gov_ru_getdocs_ip"
        or metadata.get("archive_downloaded") is not True
        or metadata.get("getdocs_status") != "completed"
        or metadata.get("subsystem_type") != "PRIZ"
        or metadata.get("token_owner") != "individual"
        or metadata.get("archive_source_host") != _EIS_HOST
        or not _NOTICE_NO.fullmatch(number)
    ):
        raise ValueError("Run is not a completed trusted original EIS getDocsIP import")
    folder = get_demo_run_input_dir(run_id)
    archive_bytes = _archive_bytes(folder)
    version, (notice, original_xml_sha) = _current_notice_from_archive(archive_bytes, number)
    valid = []
    for item in metadata.get("files", []):
        if not isinstance(item, dict) or item.get("source_type") not in _ALLOWED_TYPES:
            continue
        original_name = str(item.get("original_name") or "")
        relative = str(item.get("stored_name") or "")
        url = urlsplit(str(item.get("source_url") or ""))
        uid = parse_qs(url.query).get("uid", [])
        if (
            not original_name.lower().endswith(".docx")
            or url.scheme != "https"
            or url.hostname != _DOCUMENT_HOST
            or url.port is not None
            or url.path != "/44fz/filestore/public/1.0/download/priz/file.html"
            or len(uid) != 1
        ):
            continue
        # Source UID/name/size must match latest original EIS notice, never a
        # previous revision XML or a manually uploaded similarly-named file.
        matching = [
            att for att in notice.iter() if _local_name(att.tag) == "attachmentInfo"
            and _first(att, "publishedContentId") == uid[0]
            and _first(att, "fileName") == original_name
        ]
        if len(matching) != 1:
            continue
        doc = _regular_inside(folder, relative)
        if doc.stat().st_size > _MAX_FILE or doc.stat().st_size != int(_first(matching[0], "fileSize") or "-1"):
            continue
        doc_bytes = doc.read_bytes()
        try:
            tables = _docx_rows(doc_bytes)
            _score_table(tables)
            _contract_rules(tables)
        except (ValueError, KeyError, OSError):
            continue  # Another DOCX, not the scoring procedure
        receipt = OriginalScoringEvidence(
            schema_version="eis-original-scoring-receipt-v1",
            procurement_number=number,
            procurement_law="44fz",
            notice_version=version,
            original_soap_archive_sha256=hashlib.sha256(archive_bytes).hexdigest(),
            original_notice_xml_sha256=original_xml_sha,
            scoring_document_uid=uid[0],
            scoring_document_sha256=hashlib.sha256(doc_bytes).hexdigest(),
        )
        criterion = extract_official_qualification_criterion(
            original_archive_bytes=archive_bytes,
            original_scoring_docx_bytes=doc_bytes,
            trusted_receipt=receipt,
            analysis_date=analysis_date,
        )
        valid.append(criterion)
    if len(valid) != 1:
        raise ValueError("No unique original source-scored qualification document in current EIS run")
    return valid[0]


def assess_owned_run_qualification(
    session: Session, *, run_id: str, customer_id: str, as_of: date
) -> dict:
    """Preserve missing/unknown evidence as such; do not invent a NO_GO."""
    base = {
        "run_id": run_id,
        "source_status": "ORIGINAL_EIS_TRANSPORT_CORRELATED_SIGNATURE_NOT_VERIFIED",
        "electronic_signature_validated": False,
        "human_gold": False,
        "legal_eligibility_assessed": False,
        "external_action_allowed": False,
    }
    try:
        criterion = discover_run_criterion(run_id, analysis_date=as_of)
    except (ValueError, OSError, KeyError) as exc:
        return {
            **base,
            "source_status": "ORIGINAL_SOURCE_UNAVAILABLE_OR_UNSUPPORTED",
            "competitive_recommendation": "NOT_ASSESSED",
            "qualifying_contracts": None,
            "source_error_code": type(exc).__name__,
            "message": "Исходный документ оценки не подтверждён; квалификация требует ручной проверки.",
        }
    assessment = assess_company_qualification(
        session, customer_id=customer_id, criterion=criterion
    )
    return {
        **base,
        "source_status": "ORIGINAL_EIS_TRANSPORT_CORRELATED_SIGNATURE_NOT_VERIFIED",
        "competitive_recommendation": (
            "NO_GO" if assessment.recommendation == "NO_GO_QUALIFICATION_COMPETITIVENESS"
            else "HUMAN_REVIEW_REQUIRED"
        ),
        "qualifying_contracts": assessment.qualifying_contracts,
        "qualification_assessment": assessment.model_dump(mode="json"),
        "criterion_source": criterion.model_dump(mode="json"),
        "message": (
            "Квалификационная конкурентоспособность: NO_GO; правовой допуск не оценён."
            if assessment.recommendation == "NO_GO_QUALIFICATION_COMPETITIVENESS"
            else "Квалификационная конкурентоспособность требует проверки."
        ),
    }
