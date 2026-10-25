"""Reuse Tender Operator's proven public EIS 223 document-page downloader.

SOAP XML offers an original authoritative notice guid and filename provenance;
the public EIS notice documents page publishes current binary filestore UID
links. Old SOAP XML download ids often return 404 and MUST NOT be synthesized.

This module only matches files already present in the SHA-verified original
notice/protocol XML, and downloads through the existing verified-TLS,
allowlisted, bounded Tender Operator attachment downloader. No silent
contract/winner inference and no automatic Data Platform indexing.
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from src.modules.market_intelligence.eis_attachment_manifest import (
    _public_filestore_digest,
)
from src.modules.market_intelligence.eis_source_ledger import (
    _first,
    _local,
    _text,
    extract_archive,
)
from src.modules.market_intelligence.eis_zip_members import (
    stage_official_zip_children,
)
from src.modules.tender_operator_agent_demo.attachment_downloader import (
    AttachmentDownloadResult,
    AttachmentTransport,
    download_procurement_attachments,
)
from src.modules.tender_operator_agent_demo.procurement_schemas import (
    ProcurementAttachment,
)
from src.tender_research.providers.public_44fz_search import (
    PublicSearchStatus,
    PublicTenderDetail,
)
from src.tender_research.providers.public_223fz_search import (
    Public223FzSearchProvider,
)

MAX_ARCHIVE_XML_MEMBERS = 10000
MAX_EIS_PUBLIC_PAGES = 8
MAX_NATIVE_ATTACHMENTS = 40
ALLOWED_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _name_key(text: str) -> str:
    return " ".join(text.split()).casefold()


def _original_filename_bindings(
    archive_path: Path, source_rows: list[dict],
    registry_number: str,
) -> tuple[list[str], dict[str, list[dict[str, str]]]]:
    """Extract GUID + filename/XML source binding from validated original ZIP."""
    known_members = {
        (row["source"]["xml_member"], row["source"]["xml_sha256"])
        for row in source_rows
    }
    guids: list[str] = []
    filenames: dict[str, list[dict[str, str]]] = {}
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_XML_MEMBERS:
            raise ValueError("Source ZIP entry budget exceeded")
        for info in infos:
            if not info.filename.lower().endswith(".xml") or info.is_dir():
                continue
            xml_bytes = archive.read(info)
            xml_sha = hashlib.sha256(xml_bytes).hexdigest()
            if (info.filename, xml_sha) not in known_members:
                raise ValueError("Original XML failed source provenance check")
            root = ET.fromstring(xml_bytes)
            kind = _local(root.tag)
            if kind.startswith("purchaseNotice"):
                data = _first(root, f"body/item/{kind}Data")
                if data is None or _text(data, "registrationNumber") != registry_number:
                    continue
                guid = _text(data, "guid")
                if guid and ALLOWED_UUID.fullmatch(guid) and guid not in guids:
                    guids.append(guid)
            elif not kind.startswith("purchaseProtocol"):
                continue
            else:
                data = _first(root, f"body/item/{kind}Data")
                if data is None or _text(data, "purchaseInfo/purchaseNoticeNumber") != registry_number:
                    continue
            for node in data.iter():
                if _local(node.tag) != "document":
                    continue
                name = _text(node, "fileName")
                if not name:
                    continue
                key = _name_key(name)
                binding = {
                    "source_xml_sha256": xml_sha,
                    "source_xml_member": info.filename,
                    "original_filename_sha256": hashlib.sha256(name.encode()).hexdigest(),
                    "original_document_kind": kind,
                }
                if binding not in filenames.setdefault(key, []):
                    filenames[key].append(binding)
    return guids, filenames


def acquire_223fz_eis_attachments(
    *, registry_number: str, archive_path: Path, archive_sha256: str,
    region: str, source_date: str,
    target_dir: Path, max_attachments: int = 20,
    max_file_bytes: int = 32 * 1024 * 1024,
    max_total_bytes: int = 128 * 1024 * 1024,
    fetch_detail: Callable[..., PublicTenderDetail] | None = None,
    transport: AttachmentTransport | None = None,
    expand_zip_archives: bool = True,
) -> dict[str, object]:
    """Download only original-source-bound official 223-FZ attachments.

    Output is redacted: no public UID/id tokens or raw URLs. File paths and
    source SHA are retained locally for authorized ingestion. If source HTML
    exposes multiple revisions, downloaded bytes are marked for review.
    """
    if not re.fullmatch(r"[0-9]{11}", registry_number):
        raise ValueError("223-FZ registry number must be 11 digits")
    if not 1 <= max_attachments <= MAX_NATIVE_ATTACHMENTS:
        raise ValueError("Attachment count budget exceeded")
    if not 1 <= max_file_bytes <= 64 * 1024 * 1024:
        raise ValueError("Invalid single file budget")
    if not 1 <= max_total_bytes <= 256 * 1024 * 1024:
        raise ValueError("Invalid total file budget")
    source_rows = extract_archive(
        archive_path, official_archive_sha256=archive_sha256,
        subsystem="RI223", region=region, exact_date=source_date,
    )
    guids, source_names = _original_filename_bindings(
        archive_path, source_rows, registry_number,
    )
    if len(guids) > MAX_EIS_PUBLIC_PAGES:
        raise ValueError("Official notice revision count exceeds verified budget")
    if not guids or not source_names:
        return {
            "registry_number": registry_number,
            "status": "source_notice_guid_or_attachments_missing",
            "downloaded_count": 0,
            "records": [],
        }
    page_fetcher = fetch_detail or Public223FzSearchProvider().fetch_detail
    source_guid_count = len(guids)
    selected: list[ProcurementAttachment] = []
    seen_links: set[str] = set()
    page_hashes: list[str] = []
    errors: list[str] = []
    revision_review = source_guid_count > 1
    for guid in guids[:MAX_EIS_PUBLIC_PAGES]:
        url = (
            "https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?"
            + urlencode({"purchaseNoticeNumber": registry_number, "noticeGuid": guid})
        )
        # Existing provider has verified TLS, direct no-proxy for EIS and
        # official domain allowlisting. Never construct a guessed file uid.
        detail = page_fetcher(card_url=url, registry_number=registry_number)
        if detail.network_status != PublicSearchStatus.SUCCESS:
            errors.append("public_documents_page_unavailable")
            continue
        page_html = detail.common_info_html or ""
        page_hashes.append(hashlib.sha256(page_html.encode()).hexdigest())
        revision_review = revision_review or "revision_state_ambiguous" in (
            detail.raw.get("review_reasons") or []
        )
        for link in detail.document_links:
            filename = link.file_name or ""
            bindings = source_names.get(_name_key(filename))
            if not bindings:
                continue
            if not link.url:
                continue
            url_sha = _public_filestore_digest(link.url)
            if not url_sha or url_sha in seen_links:
                continue
            seen_links.add(url_sha)
            selected.append(ProcurementAttachment(
                attachment_id=url_sha,
                name=filename,
                url=link.url,
                can_download=True,
                provenance={
                    "source_regime": "223fz",
                    "archive_sha256": archive_sha256,
                    "xml_sha256": bindings[0]["source_xml_sha256"],
                    "xml_member": bindings[0]["source_xml_member"],
                    "original_binding_count": len(bindings),
                    "url_sha256": url_sha,
                    "public_html_sha256": page_hashes[-1],
                    "notice_guid_sha256": hashlib.sha256(guid.encode()).hexdigest(),
                    "revision_requires_review": revision_review,
                },
            ))
            if len(selected) >= MAX_NATIVE_ATTACHMENTS:
                break
        if len(selected) >= MAX_NATIVE_ATTACHMENTS:
            break
    if not selected:
        return {
            "registry_number": registry_number,
            "status": "no_original_source_bound_public_files",
            "source_notice_guid_count": source_guid_count,
            "public_pages_fetched": len(page_hashes),
            "errors": errors,
            "downloaded_count": 0,
            "records": [],
        }
    if target_dir.is_symlink():
        raise ValueError("Refusing symlinked download destination")
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target_dir.chmod(0o700)
    download: AttachmentDownloadResult = download_procurement_attachments(
        selected, target_dir=target_dir,
        max_attachments=max_attachments, max_file_size_bytes=max_file_bytes,
        max_total_size_bytes=max_total_bytes,
        allowed_domains={"zakupki.gov.ru"}, transport=transport,
    )
    records: list[dict[str, object]] = []
    for file in download.manifest:
        provenance = file.provenance or {}
        zip_children = None
        magic = None
        format_mismatch = False
        if file.status == "saved" and file.stored_name:
            saved_path = target_dir / file.stored_name
            with saved_path.open("rb") as stream:
                header = stream.read(12)
            if header.startswith(b"%PDF"):
                magic = "pdf"
            elif header.startswith(b"PK\x03\x04"):
                magic = "zip_or_ooxml"
            elif header.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
                magic = "legacy_ole"
            elif header.lstrip(b"\xef\xbb\xbf \r\n\t").lower().startswith((b"<!doctype", b"<html")):
                magic = "html"
            else:
                magic = "not_positively_identified"
            format_mismatch = (
                file.extension in {".doc", ".xls"} and magic == "zip_or_ooxml"
            )
            if expand_zip_archives and file.extension == ".zip" and magic == "zip_or_ooxml":
                try:
                    zip_children = stage_official_zip_children(
                        saved_path, expected_parent_sha256=file.sha256 or "",
                        target_dir=target_dir / "source_bound_zip_children",
                        max_members=150,
                        max_total_bytes=96 * 1024 * 1024,
                    )
                except (ValueError, OSError, zipfile.BadZipFile) as exc:
                    zip_children = {
                        "status": "zip_member_review_required",
                        "failure_type": type(exc).__name__,
                        "staged_members": 0,
                    }
        records.append({
            "source_xml_sha256": provenance.get("xml_sha256"),
            "original_archive_sha256": archive_sha256,
            "original_filename_sha256": hashlib.sha256(file.name.encode()).hexdigest(),
            "public_html_sha256": provenance.get("public_html_sha256"),
            "source_url_sha256": provenance.get("url_sha256"),
            "document_sha256": file.sha256,
            "extension": file.extension,
            "size_bytes": file.size_bytes,
            "status": file.status,
            "failure_code": file.error,
            "stored_name": file.stored_name,
            "revision_requires_review": bool(provenance.get("revision_requires_review")),
            "detected_binary_format": magic,
            "format_mismatch_requires_review": format_mismatch,
            "zip_children": zip_children,
            "source_legal_qualification": "official_source_file_not_a_signed_contract",
            "data_platform_indexed": False,
        })
    return {
        "schema_version": "mi-eis-native-attachment-acquisition/0.1",
        "registry_number": registry_number,
        "status": "downloaded" if download.saved else "download_failed",
        "source_notice_guid_count": source_guid_count,
        "public_pages_fetched": len(page_hashes),
        "source_bound_candidate_count": len(selected),
        "downloaded_count": len(download.saved),
        "skipped_count": len(download.skipped),
        "revision_requires_review": revision_review,
        "winner_verified": False,
        "signed_contract_price_verified": False,
        "records": records,
    }


def acquire_44fz_eis_attachments(
    *, registry_number: str, archive_path: Path, archive_sha256: str,
    region: str, source_date: str, target_dir: Path,
    max_attachments: int = 20,
    max_file_bytes: int = 32 * 1024 * 1024,
    max_total_bytes: int = 128 * 1024 * 1024,
    fetch_detail: Callable[..., PublicTenderDetail] | None = None,
    transport: AttachmentTransport | None = None,
) -> dict[str, object]:
    """44-FZ active-revision originals via existing public EIS provider/downloader.

    Fail closed on unclear active revision instead of mixing document versions.
    """
    from src.tender_research.providers.public_44fz_search import (
        Public44FzSearchProvider,
    )

    if not re.fullmatch(r"[0-9]{19,20}", registry_number):
        raise ValueError("44-FZ registry number must be 19-20 digits")
    if not 1 <= max_attachments <= MAX_NATIVE_ATTACHMENTS:
        raise ValueError("Attachment count budget exceeded")
    if not 1 <= max_file_bytes <= 64 * 1024 * 1024:
        raise ValueError("Invalid single file budget")
    if not 1 <= max_total_bytes <= 256 * 1024 * 1024:
        raise ValueError("Invalid total file budget")

    rows = extract_archive(
        archive_path, official_archive_sha256=archive_sha256,
        subsystem="PRIZ", region=region, exact_date=source_date,
    )
    known = {
        (row["source"]["xml_member"], row["source"]["xml_sha256"])
        for row in rows if row["record_kind"] == "notice"
        and row["notice_number"] == registry_number
    }
    if not known:
        raise ValueError("Original 44-FZ source notice not found or number mismatch")
    bound_names: dict[str, list[dict[str, str]]] = {}
    with zipfile.ZipFile(archive_path) as bundle:
        for info in bundle.infolist():
            if not info.filename.lower().endswith(".xml") or info.is_dir():
                continue
            body = bundle.read(info)
            digest = hashlib.sha256(body).hexdigest()
            if (info.filename, digest) not in known:
                continue
            root = ET.fromstring(body)
            for element in root.iter():
                if _local(element.tag) not in ("attachmentInfo", "document"):
                    continue
                name = _text(element, "fileName")
                if not name:
                    continue
                key = _name_key(name)
                entry = {"xml_sha256": digest, "xml_member": info.filename}
                if entry not in bound_names.setdefault(key, []):
                    bound_names[key].append(entry)

    detail = (fetch_detail or Public44FzSearchProvider().fetch_detail)(
        registry_number=registry_number,
    )
    if detail.network_status != PublicSearchStatus.SUCCESS:
        return {
            "registry_number": registry_number, "status": "public_documents_unavailable",
            "downloaded_count": 0, "records": [],
        }
    choice = detail.raw.get("document_revision_selection") or {}
    if choice.get("status") != "active_revision_selected" or choice.get("requires_review"):
        return {
            "registry_number": registry_number, "status": "active_revision_requires_review",
            "downloaded_count": 0, "records": [],
        }
    selected = []
    seen = set()
    html_sha = hashlib.sha256((detail.documents_html or "").encode()).hexdigest()
    for item in detail.document_links:
        filename = item.file_name or ""
        bindings = bound_names.get(_name_key(filename))
        if not bindings or not item.url:
            continue
        url_sha = _public_filestore_digest(item.url)
        if not url_sha or url_sha in seen:
            continue
        seen.add(url_sha)
        selected.append(ProcurementAttachment(
            attachment_id=url_sha, name=filename, url=item.url,
            can_download=True,
            provenance={
                "source_regime": "44fz",
                "archive_sha256": archive_sha256,
                "xml_sha256": bindings[0]["xml_sha256"],
                "source_member": bindings[0]["xml_member"],
                "public_page_sha256": html_sha,
                "download_url_sha256": url_sha,
                "active_revision": choice.get("active_revision", {}).get("revision"),
            },
        ))
        if len(selected) >= MAX_NATIVE_ATTACHMENTS:
            break
    if not selected:
        return {
            "registry_number": registry_number, "status": "no_primary_source_bound_active_files",
            "downloaded_count": 0, "records": [],
        }

    if target_dir.is_symlink():
        raise ValueError("Refusing symlinked download destination")
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target_dir.chmod(0o700)
    download = download_procurement_attachments(
        selected, target_dir=target_dir, max_attachments=max_attachments,
        max_file_size_bytes=max_file_bytes, max_total_size_bytes=max_total_bytes,
        allowed_domains={"zakupki.gov.ru"}, transport=transport,
    )
    output = []
    for item in download.manifest:
        prov = item.provenance or {}
        children = None
        if item.status == "saved" and item.extension == ".zip" and item.stored_name:
            try:
                children = stage_official_zip_children(
                    target_dir / item.stored_name,
                    expected_parent_sha256=item.sha256 or "",
                    target_dir=target_dir / "source_bound_zip_children",
                    max_members=150, max_total_bytes=96 * 1024 * 1024,
                )
            except (ValueError, OSError, zipfile.BadZipFile) as exc:
                children = {"status": "zip_review_required", "error_type": type(exc).__name__}
        output.append({
            "original_archive_sha256": archive_sha256,
            "source_xml_sha256": prov.get("xml_sha256"),
            "public_documents_html_sha256": html_sha,
            "official_url_sha256": prov.get("download_url_sha256"),
            "file_sha256": item.sha256,
            "status": item.status,
            "error": item.error,
            "stored_name": item.stored_name,
            "extension": item.extension,
            "size_bytes": item.size_bytes,
            "zip_children": children,
            "data_platform_indexed": False,
            "winner_verified": False,
        })
    return {
        "schema_version": "mi-eis-44fz-native-file-acquisition/0.1",
        "registry_number": registry_number,
        "status": "downloaded" if download.saved else "download_failed",
        "active_revision": choice.get("active_revision", {}).get("revision"),
        "source_bound_candidate_count": len(selected),
        "downloaded_count": len(download.saved),
        "skipped_count": len(download.skipped),
        "winner_verified": False,
        "signed_contract_price_verified": False,
        "records": output,
    }
