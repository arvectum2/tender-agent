"""Bounded original-EIS ZIP + externally linked attachment audit.

A fresh getDocsIP response and filestore downloads prove *retrieved bytes at a
time*, never the current legal notice status, signature or an approved bid.
Saved URLs (including query strings) never appear in audit receipts.
"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from src.modules.tender_operator_agent_demo.eis_notice_parser import (
    extract_notice_attachments,
)
from src.modules.tender_operator_agent_demo.eis_official_procedure import (
    classify_official_eis_archive,
)
from src.modules.tender_operator_agent_demo.operator_stored_file_paths import (
    checked_original_input_path,
)
from src.modules.tender_operator_agent_demo.upload_service import (
    get_demo_run_input_dir,
    get_demo_run_procurement_dir,
    load_demo_run_metadata,
)

RECEIPT_NAME = "archived_eis_source_integrity_receipt.json"
MAX_BINARY_BYTES = 20 * 1024 * 1024
MAX_NOTICE_BYTES = 2 * 1024 * 1024


class SourceIntegrityError(ValueError):
    """Official saved-source linkage cannot be independently corroborated."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _original_file(directory: Path, name: object) -> Path:
    try:
        return checked_original_input_path(directory, name)
    except (OSError, ValueError) as exc:
        raise SourceIntegrityError("missing or unsafe saved first-party original") from exc


def _archive_notice(run_id: str, metadata: dict[str, Any]) -> tuple[bytes, str]:
    number = metadata.get("procurement_id")
    if (metadata.get("procurement_source") != "zakupki_gov_ru_getdocs_ip"
            or not isinstance(number, str) or re.fullmatch(r"\d{19}", number) is None):
        raise SourceIntegrityError("unsupported EIS source or registry identity")
    revision = metadata.get("notice_revision_selected")
    if not isinstance(revision, dict) or revision.get("current_live_eis_verified") is not False:
        raise SourceIntegrityError("original snapshot must not claim current EIS approval")
    name = metadata.get("archive_stored_name")
    if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9._-]{1,120}\.zip", name):
        raise SourceIntegrityError("original getDocsIP ZIP not securely pinned")
    root = get_demo_run_input_dir(run_id)
    original = _original_file(root, name)
    actual = classify_official_eis_archive(original, number)
    bound = metadata.get("official_eis_procedure")
    if (not isinstance(bound, dict)
            or any(actual.get(k) != bound.get(k) for k in (
                "status", "archive_sha256", "notice_xml_sha256",
                "source_purchase_number", "source_version", "notice_type"
            ))
            or actual["status"] != "ATTESTED_COMPETITIVE"
            or actual["archive_sha256"] != metadata.get("original_getdocs_archive_sha256")):
        raise SourceIntegrityError("saved original ZIP classifier/hash conflicts with bound notice")
    version = actual["source_version"]
    if type(version) is not int or version < 1:
        raise SourceIntegrityError("ambiguous source revision")
    pattern = re.compile(
        rf"epNotification(?:EF2020|EZK2020|EOK2020)_{number}_{version}_[0-9a-fA-F]{{32}}\.xml\Z"
    )
    with zipfile.ZipFile(original) as z:
        members = [info for info in z.infolist() if pattern.fullmatch(info.filename)
                   and not info.is_dir() and info.file_size <= MAX_NOTICE_BYTES]
        if len(members) != 1:
            raise SourceIntegrityError("ambiguous original notice archive members")
        xml = z.read(members[0])
    if _sha(xml) != actual["notice_xml_sha256"]:
        raise SourceIntegrityError("original notice XML checksum mismatch")
    matches = [
        file for file in metadata.get("files") or []
        if file.get("original_name") == members[0].filename
        and file.get("extension") == ".xml"
        and file.get("size_bytes") == len(xml)
        and _original_file(root, file.get("stored_name")).read_bytes() == xml
    ]
    if len(matches) != 1:
        raise SourceIntegrityError("stored XML not equal to first-party ZIP notice")
    return xml, actual["archive_sha256"]


def _official_link(raw: object) -> str:
    if not isinstance(raw, str) or not raw:
        raise SourceIntegrityError("original XML attachment has no URL")
    url = urljoin("https://zakupki.gov.ru", raw)
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "zakupki.gov.ru"
            or parsed.username or parsed.password or parsed.fragment
            or parsed.path != "/44fz/filestore/public/1.0/download/priz/file.html"
            or not parsed.query):
        raise SourceIntegrityError("original attachment URL outside official filestore")
    return url


def verify_saved_source_snapshot(run_id: str) -> dict[str, Any]:
    """No network and NO writes; bind every downloaded file to original ZIP XML."""
    meta = load_demo_run_metadata(run_id)
    xml, sha = _archive_notice(run_id, meta)
    extracted = extract_notice_attachments(xml.decode("utf-8-sig"))
    if not 1 <= len(extracted) <= 100:
        raise SourceIntegrityError("original notice has no bounded attachment inventory")
    files = [f for f in meta.get("files") or []
             if f.get("source_type") == "notice_xml_attachments"]
    if len(extracted) != len(files):
        raise SourceIntegrityError("original attachment count mismatch")
    input_dir = get_demo_run_input_dir(run_id)
    verified = []
    matched_ids = set()
    matched_urls = set()
    for ref in extracted:
        link = _official_link(ref.get("url"))
        if link in matched_urls:
            raise SourceIntegrityError("duplicate official attachment URL")
        matched_urls.add(link)
        matches = [f for f in files
                   if f.get("source_url") == link
                   and f.get("original_name") == ref.get("name")]
        if len(matches) != 1:
            raise SourceIntegrityError("original notice attachment name/URL mismatch")
        f = matches[0]
        file_id = f.get("file_id")
        if not isinstance(file_id, str) or file_id in matched_ids:
            raise SourceIntegrityError("duplicate saved attachment identity")
        matched_ids.add(file_id)
        original = _original_file(input_dir, f.get("stored_name"))
        size = original.stat().st_size
        if (not 0 < size <= MAX_BINARY_BYTES or f.get("size_bytes") != size
                or original.is_symlink()):
            raise SourceIntegrityError("missing/oversized/symlink original file")
        file_sha = _sha(original.read_bytes())
        if f.get("source_download_sha256") not in (None, file_sha):
            raise SourceIntegrityError("existing historical receipt conflicts with original bytes")
        verified.append({
            "file_id": file_id, "original_name": f["original_name"],
            "source_url_sha256": _sha(link.encode()), "saved_sha256": file_sha,
            "size_bytes": size,
        })
    if len(matched_ids) != len(files):
        raise SourceIntegrityError("duplicate or orphan saved original attachment")
    return {
        "contract_version": "archived-eis-attachment-integrity-v1",
        "run_id": run_id, "procurement_number": meta["procurement_id"],
        "archived_original_zip_sha256": sha,
        "archived_notice_version": meta["official_eis_procedure"]["source_version"],
        "archived_original_notice_xml_sha256": _sha(xml),
        "published_links": len(extracted),
        "saved_url_and_bytes_verified": len(verified),
        "files": verified,
        "current_live_notice_status_verified": False,
        "owner_legal_go": False,
    }


def fetch_current_getdocs_and_binaries(
    run_id: str, *, client: Any, observed_at: datetime | None = None
) -> dict[str, Any]:
    """Read-only EIS fetch; independent current legal publication NOT claimed."""
    receipt = verify_saved_source_snapshot(run_id)
    number = receipt["procurement_number"]
    returned = client.get_docs_by_reestr_number(number)
    urls = returned.archive_urls or ([returned.archive_url] if returned.archive_url else [])
    if returned.status != "completed" or len(urls) != 1:
        raise SourceIntegrityError("official getDocsIP result unavailable or ambiguous")
    official_url = urls[0]
    parsed = urlsplit(official_url)
    if parsed.scheme != "https" or parsed.hostname != "int.zakupki.gov.ru":
        raise SourceIntegrityError("unexpected official getDocsIP archive host")
    with tempfile.TemporaryDirectory(prefix="original-eis-readonly-") as tmp:
        result = client.download_archive(official_url, Path(tmp))
        source = _original_file(Path(tmp), result.stored_name)
        if _sha(source.read_bytes()) != receipt["archived_original_zip_sha256"]:
            raise SourceIntegrityError("fresh getDocsIP original ZIP changed; prior edition unconfirmed")
    # Only the verified XML from a pinned original ZIP determines the binary URLs.
    meta = load_demo_run_metadata(run_id)
    xml, _ = _archive_notice(run_id, meta)
    expected = {
        _sha(_official_link(ref["url"]).encode()): _official_link(ref["url"])
        for ref in extract_notice_attachments(xml.decode("utf-8-sig"))
    }
    if len(expected) != receipt["published_links"]:
        raise SourceIntegrityError("duplicate original official filestore references")
    checks = []
    for f in receipt["files"]:
        url = expected.get(f["source_url_sha256"])
        if not url:
            raise SourceIntegrityError("original filestore URL no longer bound to notice")
        # Bound the download to the locally recorded size and reject replacement.
        blob, _ = client._http_get(
            url, headers={"User-Agent": client.settings.user_agent},
            timeout=min(30, client.settings.timeout_seconds),
            max_bytes=f["size_bytes"],
        )
        if len(blob) != f["size_bytes"] or _sha(blob) != f["saved_sha256"]:
            raise SourceIntegrityError("fresh official binary differs from archived original")
        checks.append(f["file_id"])
    receipt["fresh_getdocs_original_zip_matches"] = True
    receipt["fresh_official_filestore_bytes_match"] = len(checks)
    receipt["fresh_observation_utc"] = (
        observed_at or datetime.now(UTC)
    ).astimezone(UTC).isoformat()
    receipt["live_archive_retrieval_is_not_a_legal_notice_status_check"] = True
    return receipt


def verified_saved_observation(run_id: str) -> dict[str, Any] | None:
    """Project saved transport observation only while local source bytes still match."""
    target = get_demo_run_procurement_dir(run_id) / RECEIPT_NAME
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 65_536:
        return None
    try:
        raw = json.loads(target.read_text("utf-8"))
        known = verify_saved_source_snapshot(run_id)
        if not isinstance(raw, dict) or any(raw.get(k) != known[k] for k in known):
            return None
        if (raw.get("fresh_getdocs_original_zip_matches") is not True
                or raw.get("fresh_official_filestore_bytes_match") != known["published_links"]
                or raw.get("current_live_notice_status_verified") is not False
                or raw.get("owner_legal_go") is not False
                or not isinstance(raw.get("fresh_observation_utc"), str)):
            return None
        datetime.fromisoformat(raw["fresh_observation_utc"])
    except (OSError, ValueError, TypeError, KeyError, SourceIntegrityError):
        return None
    return {
        "state": "archived_originals_retrieved_byte_identical",
        "verified_at_utc": raw["fresh_observation_utc"],
        "official_attachment_count": known["published_links"],
        "official_binary_match_count": raw["fresh_official_filestore_bytes_match"],
        "archived_notice_version": known["archived_notice_version"],
        "current_live_notice_status_verified": False,
        "owner_legal_go": False,
    }
