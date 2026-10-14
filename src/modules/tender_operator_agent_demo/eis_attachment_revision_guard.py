"""General-purpose evidence and attachment-change guard for official EIS revisions.

No procurement IDs, document names, tender types, preselected phrases, or
expected amendment counts are embedded here. A match of attachment UID only
proves an identical official reference, not equality of bytes or legal meaning.
"""
from __future__ import annotations

import hashlib
import re
import zipfile
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
UID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


def _validate_manifest(manifest: Mapping[str, Mapping[str, Any]]) -> None:
    for uid, attachment in manifest.items():
        if not isinstance(uid, str) or UID.fullmatch(uid) is None:
            raise ValueError("Malformed original attachment identifier")
        if attachment.get("publishedContentId") != uid:
            raise ValueError("Original attachment UID does not match manifest key")
        name = attachment.get("fileName")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Original attachment missing source filename")
        try:
            size = int(attachment["fileSize"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Original attachment missing size") from exc
        if size <= 0 or size > 100_000_000:
            raise ValueError("Original attachment invalid size")


def compare_official_attachment_manifests(
    old: Mapping[str, Mapping[str, Any]], new: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Describe arbitrary additions, removals and unchanged UID references.

    Never assume replaced documents come in 1:1 pairs. A changed metadata
    tuple under the same UID is a source-inconsistency flag, not unchanged.
    """
    _validate_manifest(old)
    _validate_manifest(new)
    old_ids, new_ids = set(old), set(new)
    reused = old_ids & new_ids
    mismatched = sorted(
        uid for uid in reused if (
            old[uid]["fileName"] != new[uid]["fileName"]
            or int(old[uid]["fileSize"]) != int(new[uid]["fileSize"])
        )
    )
    return {
        "added_ids": sorted(new_ids - old_ids),
        "removed_ids": sorted(old_ids - new_ids),
        "retained_ids": sorted(reused - set(mismatched)),
        "same_uid_metadata_conflicts": mismatched,
        "manifest_changed": bool(old_ids ^ new_ids or mismatched),
        "requires_fresh_clause_review": bool(old_ids ^ new_ids or mismatched),
        "full_legal_review_signed": False,
    }


def verify_new_original_binary(
    uid: str, attachment: Mapping[str, Any], receipt: Mapping[str, Any],
    local_file: Path,
) -> dict[str, Any]:
    """Fail closed on absent or substituted first-party binary bytes."""
    if attachment.get("publishedContentId") != uid or receipt.get("source_uid") != uid:
        raise ValueError("Source attachment identity mismatch")
    if receipt.get("status") != "FIRST_PARTY_BINARY_VERIFIED":
        raise ValueError("New original binary has no verified receipt")
    data = local_file.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if (
        attachment.get("fileName") != receipt.get("file_name")
        or int(attachment["fileSize"]) != len(data)
        or receipt.get("file_size") != len(data)
        or not isinstance(receipt.get("sha256"), str)
        or SHA256.fullmatch(receipt["sha256"]) is None
        or receipt["sha256"] != digest
    ):
        raise ValueError("New official binary SHA/size or filename mismatch")
    return {
        "filename": attachment["fileName"],
        "size_bytes": len(data),
        "sha256": digest,
        "binary_verified": True,
        "full_legal_scope_review_signed": False,
    }


def prior_clause_evidence_applicability(
    *, original_uid: str, original_sha256: str,
    current_manifest: Mapping[str, Mapping[str, Any]],
    independently_verified_current_sha256: Mapping[str, str],
) -> str:
    """Classify *one* old clause citation, without generalizing one case to all.

    If the UID persists but its bytes have not been checked in the new
    official edition, the result is UNKNOWN rather than 'current'.
    """
    _validate_manifest(current_manifest)
    if not isinstance(original_sha256, str) or SHA256.fullmatch(original_sha256) is None:
        raise ValueError("Invalid original source SHA")
    if original_uid not in current_manifest:
        return "STALE_SOURCE_REFERENCE"
    current_hash = independently_verified_current_sha256.get(original_uid)
    if current_hash is None:
        return "UNKNOWN_CURRENT_BINARY_NOT_VERIFIED"
    if not isinstance(current_hash, str) or SHA256.fullmatch(current_hash) is None:
        raise ValueError("Invalid current original SHA")
    if current_hash != original_sha256:
        return "STALE_SOURCE_BINARY_CHANGED"
    return "CURRENT_BINARY_EXACT_MATCH_LEGAL_MEANING_NOT_SIGNED"


def matching_payload_groups(originals: Mapping[str, Path]) -> list[dict[str, Any]]:
    """Group byte-identical *inner* payloads, independent of outer EIS ZIP IDs.

    A ZIP containing exactly the same PDF as another direct attachment does
    not supply a second independent document. This is a SHA fact, not NLP.
    """
    if len(originals) > 100:
        raise ValueError("Too many original binary attachments in one group")
    matches: dict[str, list[str]] = defaultdict(list)
    for name, location in sorted(originals.items()):
        if not name or not isinstance(name, str) or not location.is_file():
            raise ValueError("Missing original binary attachment for content comparison")
        suffix = location.suffix.lower()
        if suffix == ".zip":
            with zipfile.ZipFile(location) as container:
                members = [m for m in container.infolist() if not m.is_dir()]
                if len(members) > 100 or sum(m.file_size for m in members) > 20_000_000:
                    raise ValueError("Unsafe official ZIP member limits")
                for member in members:
                    if member.flag_bits & 0x1:
                        raise ValueError("Encrypted original ZIP member")
                    if member.file_size > 20_000_000:
                        raise ValueError("Oversize original ZIP member")
                    blob = container.read(member)
                    matches[hashlib.sha256(blob).hexdigest()].append(
                        name + " :: " + member.filename
                    )
        else:
            if location.stat().st_size > 20_000_000:
                raise ValueError("Oversize official source binary")
            matches[hashlib.sha256(location.read_bytes()).hexdigest()].append(name)
    return [
        {"sha256": digest, "source_locations": sorted(locations)}
        for digest, locations in sorted(matches.items())
        if len(locations) >= 2
    ]
