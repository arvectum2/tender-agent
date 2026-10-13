"""Auto-observe original composite EOK2020 PDF inside a trusted run (no GO/NO_GO)."""
from __future__ import annotations

import hashlib
import re
import subprocess
from datetime import date
from urllib.parse import parse_qs, urlsplit

from src.modules.company_profile_store.qualification_44_alternate_observer import (
    observe_44_alternate_pdf_text,
    verify_44_alternate_originals,
)
from src.modules.company_profile_store.qualification_original_source import (
    _first,
    _local_name,
)
from src.modules.company_profile_store.qualification_run_service import (
    _ALLOWED_TYPES,
    _DOCUMENT_HOST,
    _EIS_HOSTS,
    _NOTICE_NO,
    _RUN_ID,
    _archive_bytes,
    _current_notice_from_archive,
    _regular_inside,
)
from src.modules.tender_operator_agent_demo.upload_service import (
    get_demo_run_input_dir,
    load_demo_run_metadata,
)


def discover_run_composite_pdf_observation(
    run_id: str, *, analysis_date: date
) -> dict:
    """Source-bound single PDF rubric; never fill missing supplier evidence."""
    if not _RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid owned EIS run ID")
    metadata = load_demo_run_metadata(run_id)
    number = str(metadata.get("reestr_number") or "")
    if (
        metadata.get("procurement_source") != "zakupki_gov_ru_getdocs_ip"
        or metadata.get("archive_downloaded") is not True
        or metadata.get("getdocs_status") != "completed"
        or metadata.get("subsystem_type") != "PRIZ"
        or metadata.get("token_owner") != "individual"
        or metadata.get("archive_source_host") not in _EIS_HOSTS
        or not _NOTICE_NO.fullmatch(number)
    ):
        raise ValueError("Missing trusted original 44-FZ getDocsIP run metadata")
    folder = get_demo_run_input_dir(run_id)
    archive = _archive_bytes(folder, metadata)
    version, (notice, xml_sha) = _current_notice_from_archive(archive, number)
    observations = []
    for item in metadata.get("files", []):
        if not isinstance(item, dict) or item.get("source_type") not in _ALLOWED_TYPES:
            continue
        name = str(item.get("original_name") or "")
        if not name.lower().endswith(".pdf") or not re.search("оценк|критери", name, re.I):
            continue
        url = urlsplit(str(item.get("source_url") or ""))
        uid = parse_qs(url.query).get("uid", [])
        if (
            url.scheme != "https"
            or url.hostname != _DOCUMENT_HOST
            or url.port is not None
            or url.path != "/44fz/filestore/public/1.0/download/priz/file.html"
            or len(uid) != 1
            or parse_qs(url.query) != {"uid": uid}
        ):
            continue
        matching = [
            node for node in notice.iter()
            if _local_name(node.tag) == "attachmentInfo"
            and _first(node, "publishedContentId") == uid[0]
            and _first(node, "fileName") == name
        ]
        if len(matching) != 1:
            continue
        local = _regular_inside(folder, str(item.get("stored_name") or ""))
        if (
            local.stat().st_size > 8 * 1024 * 1024
            or str(local.stat().st_size) != _first(matching[0], "fileSize")
        ):
            raise ValueError("Source-linked PDF was modified or oversized")
        expected_sha = item.get("source_download_sha256")
        if not isinstance(expected_sha, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
            continue  # Older runs without download-time source SHA are unsupported.
        payload = local.read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected_sha:
            raise ValueError("Source-linked original PDF changed after EIS download")
        original = {
            "procurement_number": number,
            "procurement_law": "44fz",
            "procurement_notice_version": version,
            "original_soap_archive_sha256": hashlib.sha256(archive).hexdigest(),
            "original_notice_xml_sha256": xml_sha,
            "scoring_document_uid": uid[0],
            "scoring_document_sha256": expected_sha,
            "scoring_document_name": name,
            "scoring_document_size_bytes": len(payload),
            "original_application_deadline": _first(notice, "endDT"),
        }
        source = verify_44_alternate_originals(
            soap_archive_bytes=archive,
            scoring_pdf_bytes=payload,
            receipt=original,
        )
        if not payload.startswith(b"%PDF-"):
            raise ValueError("Not an original bounded PDF scoring document")
        result = subprocess.run(
            ["pdftotext", "-layout", "-", "-"],
            input=payload, capture_output=True, timeout=20, check=True,
        )
        if len(result.stdout) > 1_000_000:
            raise ValueError("Unbounded PDF text extracted from original")
        try:
            observation = observe_44_alternate_pdf_text(result.stdout.decode("utf-8"))
        except (ValueError, UnicodeError):
            continue  # A document whose scoring format we do not support.
        observations.append({**source, **observation})
    if len(observations) != 1:
        raise ValueError("No unique supported original composite PDF methodology")
    return {**observations[0], "observation_as_of": analysis_date.isoformat()}
