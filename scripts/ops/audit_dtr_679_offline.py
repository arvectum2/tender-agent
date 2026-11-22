"""Bounded, NO-NETWORK, NO-DATABASE filesystem audit for DTR issue #679.

Usage: python scripts/ops/audit_dtr_679_offline.py --source-root /path/to/existing/eis
No output contains signed source URLs, filenames or source bytes. Historical
EIS HTML cannot prove the current official notice revision or DOCX originals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

from src.tender_research.providers.public_44fz_search import (
    _select_current_revision_document_links,
)
from src.tender_research.rag.missing_attachments import _official_url

CASES = (
    "0173100007526000046",
    "0128200000126007559",
    "0128200000126007558",
)
# Verified as archived first-party bytes on 2026-11-20; not live/current sources.
ARCHIVED_RECEIPTS: dict[str, dict[str, tuple[str, int]]] = {
    "0128200000126007558": {
        "public_detail_documents.html": (
            "035bcca3adb2855d98e4b31f466d071c10f369aa9ac899e640a10eb8a23cfa26",
            143222,
        ),
        "public_detail_common_info.html": (
            "b1deaa5af45932bc984689fc66460674899a7cb349dfc5ad027bed3a470ea379",
            216571,
        ),
    },
}
MAX_FILES = 100
MAX_HTML_BYTES = 1024 * 1024


class OfflineEvidenceError(ValueError):
    """No untrusted paths/URLs/exception text in public error responses."""


def _regular_bytes(path: Path, *, length: int, expected_sha: str) -> bytes:
    if (path.is_symlink() or path.parent.is_symlink() or not path.is_file()
            or length <= 0 or length > MAX_HTML_BYTES):
        raise OfflineEvidenceError("source_missing_or_unsafe")
    if path.stat().st_size != length:
        raise OfflineEvidenceError("source_length_mismatch")
    data = path.read_bytes()
    if len(data) != length or hashlib.sha256(data).hexdigest() != expected_sha:
        raise OfflineEvidenceError("source_hash_mismatch")
    return data


def audit_case(
    root: Path,
    registry: str,
    *,
    receipts: Mapping[str, Mapping[str, tuple[str, int]]] = ARCHIVED_RECEIPTS,
    expected_links: int = 4,
) -> dict:
    """Never read the database or access HTTP; no live source is attested."""
    if registry not in CASES or not re.fullmatch(r"\d{19}", registry):
        raise ValueError("unrecognized issue scope")
    record = {
        "registry_number": registry,
        "readiness": "BLOCKED",
        "current_official_revision_verified": False,
        "archived_html_sha_size_verified": False,
        "historical_revision_verified": False,
        "historical_attachment_count": 0,
        "verified_original_docx_count": 0,
        "original_bytes_sha_verified": False,
        "local_original_candidates": 0,
        "local_source_files": 0,
        "disposition": "source_unavailable",
    }
    if not root.is_dir() or root.is_symlink():
        record["disposition"] = "unsafe_source_root"
        return record
    folder = root / registry
    if folder.is_symlink():
        record["disposition"] = "unsafe_case_directory"
        return record
    if not folder.is_dir():
        return record
    try:
        # Metadata only: no parsing or trusting arbitrary files, and no
        # traversal into symlinks or unbounded directory inventories.
        files = []
        for entry in folder.rglob("*"):
            if entry.is_symlink():
                raise OfflineEvidenceError("unsafe_file_entry")
            if entry.is_file():
                files.append(entry)
                if len(files) > MAX_FILES:
                    raise OfflineEvidenceError("source_inventory_unbounded")
        record["local_source_files"] = len(files)
        originals_dir = folder / "documents" / "original"
        if originals_dir.is_symlink():
            raise OfflineEvidenceError("unsafe_original_directory")
        record["local_original_candidates"] = sum(
            path.parent == originals_dir for path in files
        )
        if registry not in receipts:
            if files:
                record["disposition"] = "unreconciled_local_evidence"
            return record

        archived = {}
        for name, (sha, length) in receipts[registry].items():
            if name not in {"public_detail_common_info.html", "public_detail_documents.html"}:
                raise OfflineEvidenceError("invalid_pinned_receipt_name")
            archived[name] = _regular_bytes(folder / "raw" / name, length=length, expected_sha=sha)
        record["archived_html_sha_size_verified"] = True
        docs_html = archived["public_detail_documents.html"].decode("utf-8")
        page_url = (
            "https://zakupki.gov.ru/epz/order/notice/ea20/view/documents.html"
            f"?regNumber={registry}"
        )
        links, revisions, choice = _select_current_revision_document_links(docs_html, page_url)
        unique_official = (
            len(links) == expected_links
            and len({link.url for link in links}) == expected_links
            and all(_official_url(link.url) for link in links)
        )
        active = [r for r in revisions if r.active is True and r.revision == 1]
        archive_verified = (
            choice.get("status") == "active_revision_selected"
            and choice.get("requires_review") is False
            and len(revisions) == 1
            and len(active) == 1
            and unique_official
        )
        if archive_verified:
            record["historical_revision_verified"] = True
            record["historical_revision_number"] = 1
            record["historical_attachment_count"] = len(links)
        record["disposition"] = (
            "historical_snapshot_only_original_bytes_unavailable"
            if archive_verified and not record["local_original_candidates"]
            else "manual_source_reconciliation_required"
        )
        return record
    except (OfflineEvidenceError, UnicodeError, ValueError, OSError, TypeError):
        record["disposition"] = "source_evidence_unverified"
        record["historical_revision_verified"] = False
        record["historical_attachment_count"] = 0
        return record


def audit(root: Path, *, receipts: Mapping[str, Mapping[str, tuple[str, int]]] = ARCHIVED_RECEIPTS) -> dict:
    if not root.is_absolute():
        raise ValueError("absolute existing source root required")
    return {
        "contract": "ta-dtr-679-offline-filesystem-audit-v1",
        "read_only": True,
        "network_requests": 0,
        "database_queries": 0,
        "original_bytes_downloaded": 0,
        "current_revision_authorized": False,
        "source_retry_authorized": False,
        "production_write_authorized": False,
        "scope": "three_nov20_dtr_missing_originals",
        "cases": [audit_case(root, number, receipts=receipts) for number in CASES],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(args.source_root)
    except (ValueError, OSError):
        print(json.dumps({"ok": False, "error_code": "offline_source_root_invalid"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
