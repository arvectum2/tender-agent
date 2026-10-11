"""Fail-closed offline reconciliation of independently downloaded EIS receipts.

Never treat page UI edition or data-platform self-reported hashes as independent
proof of authoritative EIS notice revision. No network, secret or live mutation.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit


@dataclass(frozen=True)
class Reconciliation:
    status: str
    matched_originals: int
    total_originals: int
    error_codes: tuple[str, ...]


def reconcile_receipts(
    receipts: Mapping[str, Any],
    original_bytes: Mapping[str, bytes],
    exported_resources: list[dict[str, Any]],
    *,
    independently_verified_notice_revision: str | None = None,
    expected_collection_id: str | None = None,
    expected_source_type: str | None = None,
) -> Reconciliation:
    """Hash public bytes against supplied DP exports; missing proof stays UNKNOWN.

    A valid DP document must independently match both the original-file digest
    and an explicit public filestore URI. Even exact matches cannot be called
    fully VERIFIED until a separately verified notice revision is supplied.
    """
    errors: set[str] = set()
    rows = receipts.get("files") if isinstance(receipts, Mapping) else None
    if not isinstance(rows, list) or not rows:
        return Reconciliation("UNKNOWN", 0, 0, ("MISSING_RECEIPTS",))
    if not isinstance(exported_resources, list):
        return Reconciliation("UNKNOWN", 0, len(rows), ("INVALID_DP_EXPORT",))
    matched = 0
    seen_uids: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            errors.add("INVALID_RECEIPT")
            continue
        uid, expected_digest = row.get("uid"), row.get("sha256")
        uri = row.get("url")
        if not all(isinstance(x, str) and x for x in (uid, expected_digest, uri)):
            errors.add("INVALID_RECEIPT")
            continue
        if uid in seen_uids:
            errors.add("DUPLICATE_SOURCE_UID")
            continue
        seen_uids.add(uid)
        if not re.fullmatch(r"[A-F0-9]{32}", uid) or not re.fullmatch(
            r"[a-fA-F0-9]{64}", expected_digest
        ):
            errors.add("INVALID_RECEIPT")
            continue
        parsed = urlsplit(uri)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "zakupki.gov.ru"
            or parsed.path != "/44fz/filestore/public/1.0/download/priz/file.html"
            or parsed.fragment
            or set(parse_qs(parsed.query)) != {"uid"}
            or parse_qs(parsed.query).get("uid") != [uid]
        ):
            errors.add("UNTRUSTED_SOURCE_URI")
            continue
        original = original_bytes.get(uid)
        if not isinstance(original, bytes) or not original:
            errors.add("MISSING_ORIGINAL_BYTES")
            continue
        digest = hashlib.sha256(original).hexdigest()
        if not hmac.compare_digest(digest, expected_digest.lower()):
            errors.add("RECEIPT_BINARY_MISMATCH")
            continue
        candidates = [
            r
            for r in exported_resources
            if isinstance(r, dict) and r.get("canonical_uri") == uri
        ]
        if not candidates:
            errors.add("NO_DP_SOURCE_MATCH")
            continue
        valid = [
            r
            for r in candidates
            if isinstance(r.get("content_hash"), str)
            and hmac.compare_digest(r["content_hash"].lower(), digest)
            and any(
                isinstance(d, dict)
                and isinstance(d.get("content_hash"), str)
                and hmac.compare_digest(d["content_hash"].lower(), digest)
                and d.get("document_id")
                for d in (
                    r.get("documents") if isinstance(r.get("documents"), list) else []
                )
            )
        ]
        if len(valid) != 1:
            errors.add("DP_BINARY_OR_DOCUMENT_MISMATCH")
            continue
        if not expected_collection_id or not expected_source_type:
            errors.add("INDEPENDENT_DP_IDENTITY_CONTEXT_MISSING")
            continue
        expected_resource_id = hashlib.sha256(
            f"resource\0{expected_collection_id}\0{expected_source_type}\0{uri}".encode()
        ).hexdigest()
        resource = valid[0]
        if (
            resource.get("source_type") != expected_source_type
            or resource.get("resource_id") != expected_resource_id
        ):
            errors.add("DP_RESOURCE_ID_MISMATCH")
            continue
        expected_document_id = hashlib.sha256(
            f"document\0{expected_resource_id}\0{digest}".encode()
        ).hexdigest()
        docs = resource.get("documents")
        matching_documents = [
            d
            for d in (docs if isinstance(docs, list) else [])
            if isinstance(d, dict)
            and d.get("document_id") == expected_document_id
            and isinstance(d.get("content_hash"), str)
            and hmac.compare_digest(d["content_hash"].lower(), digest)
        ]
        if len(matching_documents) != 1:
            errors.add("DP_DOCUMENT_ID_MISMATCH")
            continue
        if not independently_verified_notice_revision:
            errors.add("NOTICE_REVISION_NOT_INDEPENDENTLY_VERIFIED")
            continue
        metadata = valid[0].get("metadata")
        if (
            metadata.get("notice_revision") if isinstance(metadata, Mapping) else None
        ) != independently_verified_notice_revision:
            errors.add("DP_NOTICE_REVISION_MISMATCH")
            continue
        matched += 1
    # This check establishes source-byte concordance only; separate DP resource
    # stable ID and normalized chunk coordinate audits remain prerequisites.
    if matched == len(rows) and not errors:
        return Reconciliation(
            "SOURCE_BYTES_MATCHED_CHUNKS_UNVERIFIED", matched, len(rows), ()
        )
    return Reconciliation("UNKNOWN", matched, len(rows), tuple(sorted(errors)))
