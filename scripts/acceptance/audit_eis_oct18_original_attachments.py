"""Fixed-allowlist, first-party read-only EIS 44-FZ attachment SHA and DOCX inventory.

Only returns bounded source receipt metadata, not original binaries, signed URL
queries, contract clauses, personal data or a current legal/bid decision.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from src.modules.tender_operator_agent_demo.eis_notice_parser import (
    extract_notice_attachments,
)
from src.modules.tender_operator_agent_demo.settings import get_zakupki_soap_settings
from src.modules.tender_operator_agent_demo.zakupki_soap_client import ZakupkiSoapClient

NUMBERS = ("0163200000326005243", "0332100025426000039", "0148200002426000013")
_MAX_ARCHIVE = 8_000_000
_MAX_BINARY = 10_000_000
_MAX_UNZIPPED = 30_000_000
_XML_TAG = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"


class OriginalSourceError(ValueError):
    """Cannot attest the source or safe file structure."""


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def official_filestore(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "zakupki.gov.ru"
        and parsed.netloc == "zakupki.gov.ru"
        and parsed.path == "/44fz/filestore/public/1.0/download/priz/file.html"
        and bool(parsed.query)
        and not parsed.fragment
    )


def docx_text(original: bytes) -> str:
    """Bounded extraction of main Word body only; not complete OCR or appendices."""
    with zipfile.ZipFile(io.BytesIO(original)) as zipped:
        names = zipped.namelist()
        if "word/document.xml" not in names or len(names) > 400:
            raise OriginalSourceError("not an unambiguous Word body")
        info = zipped.getinfo("word/document.xml")
        if info.file_size > _MAX_UNZIPPED:
            raise OriginalSourceError("Word text XML too large")
        document = zipped.read(info)
    if b"<!DOCTYPE" in document.upper() or b"<!ENTITY" in document.upper():
        raise OriginalSourceError("XML external declaration")
    try:
        root = ET.fromstring(document)
    except ET.ParseError as exc:
        raise OriginalSourceError("Word XML invalid") from exc
    result = " ".join((node.text or "") for node in root.iter(_XML_TAG))
    return " ".join(result.split())[:200_000]


def magic_match(name: str, blob: bytes) -> str:
    suffix = Path(name).suffix.lower()
    if not 0 < len(blob) <= _MAX_BINARY:
        raise OriginalSourceError("empty or oversized original binary")
    if suffix == ".docx" and blob.startswith(b"PK\x03\x04"):
        docx_text(blob)
        return "DOCX_MAIN_BODY_OK"
    if suffix == ".doc" and blob.startswith(b"\xd0\xcf\x11\xe0"):
        return "LEGACY_DOC_OPAQUE_UNEXTRACTED"
    if suffix == ".zip" and blob.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            if (len(z.infolist()) > 300
                    or sum(item.file_size for item in z.infolist()) > _MAX_UNZIPPED):
                raise OriginalSourceError("unbounded nested original ZIP")
        return "ZIP_ORIGINAL_CONTAINER_UNEXTRACTED"
    if suffix == ".pdf" and blob.startswith(b"%PDF-"):
        return "PDF_BINARY_UNEXTRACTED"
    if suffix in (".xls", ".xlsx") and (
        blob.startswith((b"\xd0\xcf\x11\xe0", b"PK\x03\x04"))
    ):
        return "SHEET_BINARY_UNEXTRACTED"
    raise OriginalSourceError("unknown or conflicting original file signature")


def _audit(number: str, expected: dict, client: ZakupkiSoapClient) -> dict:
    from src.modules.tender_operator_agent_demo.eis_official_procedure import (
        classify_official_eis_archive,
    )

    response = client.get_docs_by_reestr_number(number)
    urls = response.archive_urls or ([response.archive_url] if response.archive_url else [])
    if response.status != "completed" or len(urls) != 1:
        raise OriginalSourceError("official archive is not unique or complete")
    parsed = urlsplit(urls[0])
    if parsed.scheme != "https" or parsed.hostname != "int.zakupki.gov.ru":
        raise OriginalSourceError("unexpected official getDocs host")
    with tempfile.TemporaryDirectory(prefix="ta-oct18-original-documents-") as tmp:
        downloaded = client.download_archive(urls[0], Path(tmp))
        archive = Path(tmp) / downloaded.stored_name
        if (archive.is_symlink() or not archive.is_file()
                or not 0 < archive.stat().st_size <= _MAX_ARCHIVE):
            raise OriginalSourceError("missing or excessive original ZIP")
        classified = classify_official_eis_archive(archive, number)
        bound = {
            "zip_sha256": classified.get("archive_sha256"),
            "original_xml_sha256": classified.get("notice_xml_sha256"),
            "selected_archived_version": classified.get("source_version"),
        }
        if (classified.get("status") != "ATTESTED_COMPETITIVE"
                or any(expected.get(k) != v for k, v in bound.items())):
            raise OriginalSourceError("original ZIP and XML not same frozen prior edition")
        with zipfile.ZipFile(archive) as source:
            pattern = re.compile(
                r"epNotification(?:EZK2020|EF2020|EOK2020)_"
                + re.escape(number) + "_"
                + str(classified["source_version"]) + r"_[A-Fa-f0-9]{32}\.xml\Z"
            )
            matching = [
                member for member in source.infolist()
                if pattern.fullmatch(member.filename) and not member.is_dir()
            ]
            if len(matching) != 1 or matching[0].file_size > 5_000_000:
                raise OriginalSourceError("original selected XML ambiguous")
            xml = source.read(matching[0])
        if _sha(xml) != expected["original_xml_sha256"]:
            raise OriginalSourceError("notice XML changed")
        refs = extract_notice_attachments(xml.decode("utf-8-sig"))
        if not 1 <= len(refs) <= 25:
            raise OriginalSourceError("missing/unbounded notice attachment references")
        seen = set()
        files = []
        for index, attachment in enumerate(refs, start=1):
            url, name = attachment["url"], attachment["name"]
            if not isinstance(url, str) or not official_filestore(url) or url in seen:
                raise OriginalSourceError("off-domain or duplicate external official file")
            if not isinstance(name, str) or len(name) > 240 or "/" in name or "\\" in name:
                raise OriginalSourceError("unsafe original file label")
            seen.add(url)
            blob, _ = client._http_get(
                url,
                headers={"User-Agent": client.settings.user_agent},
                timeout=min(25, client.settings.timeout_seconds),
                max_bytes=_MAX_BINARY,
            )
            kind = magic_match(name, blob)
            extracted = docx_text(blob) if kind == "DOCX_MAIN_BODY_OK" else ""
            files.append({
                "source_index": index,
                "original_name": name,
                "document_kind_hint": attachment.get("document_kind") or "unknown",
                "binary_size": len(blob),
                "binary_sha256": _sha(blob),
                "source_url_sha256": _sha(url.encode("utf-8")),
                "format_status": kind,
                "docx_main_body_extracted_length": len(extracted),
                "docx_main_body_sha256": _sha(extracted.encode("utf-8")) if extracted else None,
                "only_docx_main_body_scanned": True,
                "other_content_or_nested_attachments_unchecked": True,
            })
    return {
        "registry_number": number,
        "original_notice_version": classified["source_version"],
        "zip_sha256": bound["zip_sha256"],
        "notice_xml_sha256": bound["original_xml_sha256"],
        "official_attached_files": len(files),
        "files": files,
        "original_current_live_revision_verified": False,
        "all_document_semantics_verified": False,
        "company_eligibility_verified": False,
        "bid_ready": False,
    }


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--expected", type=Path, required=True)
    cli.add_argument("--output", type=Path)
    args = cli.parse_args()
    existing = json.loads(args.expected.read_text(encoding="utf-8"))
    originals = {row["number"]: row for row in existing["records"]}
    if (set(originals) != set(NUMBERS)
            or any(row.get("archival_evidence") != "SHA_VERIFIED_NOTICE"
                   for row in originals.values())):
        cli.error("prior frozen first-party EIS original receipt incomplete")
    settings = replace(get_zakupki_soap_settings(), timeout_seconds=25)
    if not (settings.configured and settings.disable_proxy_for_eis
            and settings.require_direct_ru_route):
        cli.error("direct RU official source transport not configured")
    client = ZakupkiSoapClient(settings, runtime_status_enabled=False)
    entries = []
    for number in NUMBERS:
        try:
            result = _audit(number, originals[number], client)
            entries.append(result)
        except (OriginalSourceError, RuntimeError, OSError, ValueError, zipfile.BadZipFile) as exc:
            entries.append({
                "registry_number": number,
                "source_state": "UNAVAILABLE_FAIL_CLOSED",
                "reason_type": type(exc).__name__,
                "official_attached_files": 0,
                "bid_ready": False,
            })
    result = {
        "contract_version": "b2b_eis_44fz_three_exact_original_attachments_v1",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "fixed_allowlist": list(NUMBERS),
        "read_only": True,
        "temporary_original_files_discarded": True,
        "exact_source_url_query_never_disclosed": True,
        "total_official_fetched_binary_attachments": sum(
            row["official_attached_files"] for row in entries
        ),
        "fully_qualifying_current_bids": 0,
        "legal_live_status_verified": False,
        "commercial_bid_actions": 0,
        "entries": entries,
    }
    data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data)
    return 0 if all("source_state" not in x for x in entries) else 2


if __name__ == "__main__":
    raise SystemExit(main())
