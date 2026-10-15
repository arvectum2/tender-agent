"""Acquire SHA-attested official original attachment bytes, not legal contents."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlsplit

from src.modules.tender_operator_agent_demo.eis_attachment_revision_guard import (
    verify_new_original_binary,
)

UID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
MAX_ATTACHMENT_SIZE = 50_000_000


def retrieve_original_binary(*, uid: str, source_item: dict, source_root: Path, fetch) -> dict:
    """Require exact official publishedContentId, HTTPS EIS URL and file size."""
    if not isinstance(uid, str) or UID.fullmatch(uid) is None:
        raise ValueError("Unsafe official attachment UID")
    if source_item.get("publishedContentId") != uid:
        raise ValueError("XML attachment UID mismatch")
    name = source_item.get("fileName")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Official source filename missing")
    try:
        size = int(source_item["fileSize"])
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError("Official source size missing") from exc
    if size <= 0 or size > MAX_ATTACHMENT_SIZE:
        raise ValueError("Unsafe official attachment source size")
    uri = urlsplit(source_item.get("url", ""))
    if uri.scheme != "https" or uri.hostname != "zakupki.gov.ru" or uri.username or uri.password:
        raise ValueError("Original source attachment URL outside official HTTPS host")
    suffix = Path(name).suffix.lower()
    if suffix not in {".zip", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".rtf", ".odt", ".txt"}:
        raise ValueError("Unknown original attached document type")
    output = source_root / (uid + suffix)
    if output.exists():
        raise ValueError("Cannot overwrite preexisting original source binary")
    payload = fetch(source_item["url"], size)
    if not isinstance(payload, bytes) or len(payload) != size:
        raise ValueError("Official original downloaded bytes do not match declared size")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    private_proof = {
        "status": "FIRST_PARTY_BINARY_VERIFIED",
        "source_uid": uid,
        "file_name": name,
        "file_size": size,
        "sha256": digest,
        "original_url_scheme": uri.scheme,
        "original_url_host": uri.hostname,
        "relative_path": output.name,
    }
    verify_new_original_binary(uid, source_item, private_proof, output)
    return private_proof
