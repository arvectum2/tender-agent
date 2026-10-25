"""Source-bound EIS public attachment metadata, never network download.

Raw EIS filestore URLs can carry opaque public download tokens. They are
validated but NOT returned. Recovery of exact URL requires the approved,
SHA-verified original XML member; this module cannot fetch arbitrary URLs.
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET

from .eis_source_ledger import (
    MAX_ARCHIVE_BYTES,
    MAX_MEMBER_BYTES,
    MAX_XML_MEMBERS,
    MAX_XML_TOTAL,
    _local,
    _text,
    extract_archive,
)

ALLOWED_EIS_FILE_PATHS = frozenset({
    "/223/filestore/public/1.0/download/fz223/file.html",
    "/44fz/filestore/public/1.0/download/priz/file.html",
    "/223/purchase/public/download/download.html",
})
MAX_ATTACHMENT_REFERENCES = 1000


def _public_filestore_digest(url: str) -> str | None:
    """Admit documented official EIS URLs only; never return raw link/query."""
    if not isinstance(url, str) or len(url) > 2048:
        return None
    try:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, strict_parsing=True)
    except ValueError:
        return None
    if (parsed.scheme != "https" or parsed.hostname != "zakupki.gov.ru"
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.fragment or parsed.path not in ALLOWED_EIS_FILE_PATHS):
        return None
    if parsed.path == "/223/purchase/public/download/download.html":
        if (set(query) != {"id"} or len(query.get("id", [])) != 1
                or not re.fullmatch(r"[0-9]{1,12}", query["id"][0])):
            return None
    elif (set(query) != {"uid"} or len(query.get("uid", [])) != 1
          or not re.fullmatch(r"[A-Fa-f0-9]{32}", query["uid"][0])):
        return None
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _sanitized_extension(name: str) -> str | None:
    if not name or len(name) > 240 or "\x00" in name:
        return None
    if "/" in name or "\\" in name or name in (".", ".."):
        return None
    suffix = Path(name).suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
        return None
    return suffix


def attachment_manifest(
    *, archive_path: Path, official_archive_sha256: str,
    subsystem: str, region: str, exact_date: str,
) -> dict[str, object]:
    """Identify secure original-source attachment references without fetching."""
    # The existing primary-source ledger verifies archive SHA, XML budget,
    # DTD safety and official transport metadata before any interpretation.
    originals = extract_archive(
        archive_path, official_archive_sha256=official_archive_sha256,
        subsystem=subsystem, region=region, exact_date=exact_date,
    )
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Archive exceeds size bound")
    included_sha = {row["source"]["xml_sha256"] for row in originals}
    found = []
    rejected = 0
    seen = set()
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) > MAX_XML_MEMBERS or sum(m.file_size for m in members) > MAX_XML_TOTAL:
            raise ValueError("Archive XML safety bounds exceeded")
        for member in members:
            if not member.filename.lower().endswith(".xml") or member.is_dir():
                continue
            if member.file_size > MAX_MEMBER_BYTES:
                raise ValueError("Original XML byte limit exceeded")
            raw = archive.read(member)
            xml_sha = hashlib.sha256(raw).hexdigest()
            if xml_sha not in included_sha:
                raise ValueError("Original XML source hash missing")
            root = ET.fromstring(raw)
            for parent in root.iter():
                tag = _local(parent.tag)
                if tag not in ("attachmentInfo", "document"):
                    continue
                filename = _text(parent, "fileName")
                url = _text(parent, "url")
                if not filename or not url:
                    continue
                digest = _public_filestore_digest(url)
                extension = _sanitized_extension(filename)
                if digest is None or extension is None:
                    rejected += 1
                    continue
                if len(found) >= MAX_ATTACHMENT_REFERENCES:
                    raise ValueError("EIS attachment references exceed bound")
                ident = (xml_sha, digest)
                if ident in seen:
                    continue
                seen.add(ident)
                found.append({
                    "xml_sha256": xml_sha,
                    "original_archive_sha256": official_archive_sha256,
                    "source_member": member.filename,
                    "source_element": tag,
                    "official_url_sha256_without_url": digest,
                    "extension": extension,
                    "source_kind": "official_eis_attachment_reference",
                    "document_content_verified": False,
                    "document_downloaded": False,
                })
    return {
        "schema_version": "mi-eis-attachment-source-manifest/0.1",
        "subsystem": subsystem,
        "exact_date": exact_date,
        "region": region,
        "official_archive_sha256": official_archive_sha256,
        "safe_reference_count": len(found),
        "rejected_untrusted_reference_count": rejected,
        "original_document_download_supported": False,
        "records": found,
    }
