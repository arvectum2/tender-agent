"""Read-only byte verification of previously captured SIBUR first-party attachments.

Historical saved receipts are evidence of earlier operations, not permission for HTTP
requests, Data Platform indexing, a current legal-status claim, or new DB writes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from scripts.research.acquire_sibur_documents import (
    MAX_BYTES,
    SUPPORTED,
    source_refs,
    type_matches,
    valid_url,
)

MAX_RECEIPT_BYTES = 64_000


def _no_duplicate_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate document receipt field")
        result[key] = value
    return result


def _references_fingerprint(references):
    if not isinstance(references, list) or not all(isinstance(x, dict) for x in references):
        raise ValueError("invalid linked original observation")
    return Counter(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in references)


def audit_saved_documents(snapshot: Path, output: Path) -> dict:
    """Fail closed unless every URL in a complete original snapshot has exact saved bytes."""
    if (not output.is_dir() or output.is_symlink()
            or output.resolve() != output):
        raise ValueError("unsafe existing private document directory")
    refs = source_refs(snapshot)  # Re-verifies all raw pages, hashes and historical rows.
    if not refs:
        raise ValueError("empty original source attachment membership")
    expected_files = {hashlib.sha256(u.encode()).hexdigest() + ".json" for u in refs}
    saved_names = {
        e.name for e in os.scandir(output)
        if re.fullmatch(r"[0-9a-f]{64}\.json", e.name)
    }
    if expected_files != saved_names:
        raise ValueError("original source URL receipt membership changed")
    extensions = Counter()
    supported_signatures = 0
    extension_mismatch = 0
    total_source_mentions = 0
    linked_file_digests = set()
    total_reported_bytes = 0
    aligned_originals = 0
    for url, observations in refs.items():
        if not valid_url(url):
            raise ValueError("unapproved original SIBUR document URL")
        name = hashlib.sha256(url.encode()).hexdigest() + ".json"
        path = output / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RECEIPT_BYTES:
            raise ValueError("missing, linked or oversized document receipt")
        receipt = json.loads(path.read_bytes(), object_pairs_hook=_no_duplicate_fields)
        if (not isinstance(receipt, dict) or receipt.get("status") != "captured"
                or receipt.get("url") != url
                or _references_fingerprint(receipt.get("references"))
                != _references_fingerprint(observations)):
            raise ValueError("receipt does not match first-party original source member")
        sha = receipt.get("sha256")
        ext = Path(urlsplit(url).path).suffix.lower()
        if (not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None
                or type(receipt.get("bytes")) is not int
                or not 0 < receipt["bytes"] <= MAX_BYTES):
            raise ValueError("invalid captured document size or SHA receipt")
        saved_name = receipt.get("file")
        filename_matches = saved_name == sha + ext
        # The 14-Nov record for one .ppt URL was saved as a .pptx blob.
        # Preserve its SHA receipt but DO NOT promote it to an original .ppt.
        known_conversion = ext == ".ppt" and saved_name == sha + ".pptx"
        if not filename_matches and not known_conversion:
            raise ValueError("captured filename is not consistent with source URL")
        if known_conversion:
            extension_mismatch += 1
        else:
            aligned_originals += 1
        body = output / receipt["file"]
        if (body.is_symlink() or not body.is_file()
                or body.stat().st_size != receipt["bytes"]):
            raise ValueError("original document body missing or size mismatch")
        with body.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != sha:
            raise ValueError("original document bytes differ from receipt SHA")
        if filename_matches and ext in SUPPORTED:
            with body.open("rb") as stream:
                magic = stream.read(8)
            if not type_matches(magic, ext):
                raise ValueError("original document body signature mismatch")
            supported_signatures += 1
        extensions[ext] += 1
        linked_file_digests.add(sha)
        total_reported_bytes += receipt["bytes"]
        total_source_mentions += len(observations)
    return {
        "status": "needs_review" if extension_mismatch else "verified_historical_offline",
        "source": "sibur_public",
        "source_urls": len(refs),
        "linked_source_observations": total_source_mentions,
        "verified_saved_receipts": len(refs),
        "source_filename_aligned_sha_verified": aligned_originals,
        "source_url_extension_mismatch_quarantined": extension_mismatch,
        "unique_original_file_sha256": len(linked_file_digests),
        "linked_file_bytes_total": total_reported_bytes,
        "supported_signature_checked": supported_signatures,
        "other_formats_sha_only": len(refs) - supported_signatures,
        "file_formats": dict(sorted(extensions.items())),
        "network_requests": 0,
        "db_mutations": 0,
        "legal_status_current_verified": False,
        "new_source_admission_authorized": False,
        "all_first_party_original_filenames_verified": extension_mismatch == 0,
    }
