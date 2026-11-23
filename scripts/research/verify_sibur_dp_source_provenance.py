"""Reproduce historical SIBUR first-party source lineage without live HTTP or DB access.

Source URL/row and original-file SHA are separate from archived DP indexing
attestation; only their conjunction verifies historical, not current, provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from scripts.research.acquire_sibur_documents import source_refs, valid_url
from scripts.research.reconciled_sibur_index import load
from src.modules.tender_connectors.sibur.archive_parser import (
    archive_url,
    replay_archived_page,
)

MAX_RECEIPT_BYTES = 64_000
MAX_ORIGINAL_BYTES = 25 * 1024 * 1024
HEX_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _unique(pairs):
    value = {}
    for key, member in pairs:
        if key in value:
            raise ValueError("duplicate original-document receipt field")
        value[key] = member
    return value


def _read_receipt(path: Path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_RECEIPT_BYTES:
        raise ValueError("unsafe historical receipt file")
    result = json.loads(path.read_bytes(), object_pairs_hook=_unique)
    if not isinstance(result, dict):
        raise TypeError("invalid original-document receipt")
    return result


def _body_sha(directory: Path, sha: str) -> None:
    if HEX_SHA.fullmatch(sha) is None:
        raise ValueError("invalid document SHA identity")
    path = directory / (sha + ".xlsx")
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_ORIGINAL_BYTES:
        raise ValueError("missing, unsafe or oversized original document")
    with path.open("rb") as src:
        if hashlib.file_digest(src, "sha256").hexdigest() != sha:
            raise ValueError("first-party original document SHA mismatch")


def _record(document_dir: Path, sha: str, url: str, receipt: dict) -> None:
    if (not valid_url(url) or Path(urlsplit(url).path).suffix.lower() != ".xlsx"
            or receipt.get("status") != "captured" or receipt.get("url") != url
            or receipt.get("sha256") != sha or receipt.get("file") != sha + ".xlsx"
            or type(receipt.get("bytes")) is not int):
        raise ValueError("archived first-party receipt and original document disagree")
    _body_sha(document_dir, sha)
    if (document_dir / (sha + ".xlsx")).stat().st_size != receipt["bytes"]:
        raise ValueError("archived original document size mismatch")


def _archive_ref(archive_root: Path, source_url: str, expected_sha: str, external_id: str,
                 source_row: str, document_url: str) -> None:
    qs = parse_qs(urlsplit(source_url).query)
    try:
        category = qs["catNMK"][0]
        page_number = int(qs["PAGEN_1"][0])
    except (KeyError, ValueError, IndexError) as exc:
        raise ValueError("archive source lacks category/page identity") from exc
    if source_url != archive_url(category, page_number):
        raise ValueError("archive source URL differs from allowlisted category/page")
    directory = archive_root / "categories" / category
    if category == "999_19":
        directory = archive_root / "support-services-20261115" / category
    original_page = replay_archived_page(directory, category, page_number)
    if original_page.sha256 != expected_sha:
        raise ValueError("source archive original page digest differs")
    matches = [r for r in original_page.records if
               r["external_id"] == external_id and r["source_row"] == source_row
               and r["source_url"] == source_url and document_url in r["documentation_urls"]]
    if len(matches) != 1:
        raise ValueError("source archive original row-to-document linkage unverified")


def verify_saved_source_lineage(registry_snapshot: Path, documents: Path,
                                archive_root: Path) -> dict:
    """Fail closed unless every historical DP document has SHA-pinned source linkage."""
    for directory in (documents, archive_root):
        if not directory.is_dir() or directory.is_symlink() or directory.resolve() != directory:
            raise ValueError("unsafe historical source directory")
    historic = load(documents)
    if not historic:
        raise ValueError("no historical DP originals to verify")
    expected = set(historic)
    verified = {}
    registry = source_refs(registry_snapshot)  # SHA-replays all pinned first-party pages.
    for url, references in registry.items():
        receipt_path = documents / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        if not receipt_path.is_file() or receipt_path.is_symlink():
            continue
        receipt = _read_receipt(receipt_path)
        sha = receipt.get("sha256")
        if sha not in expected:
            continue
        _record(documents, sha, url, receipt)
        if receipt.get("references") != references:
            raise ValueError("registry receipt differs from pinned original page observations")
        verified[sha] = ("registry", hashlib.sha256(url.encode()).hexdigest())
    archive_documents = archive_root / "categories" / "documents"
    if not archive_documents.is_dir() or archive_documents.is_symlink():
        raise ValueError("missing trusted archived source document corpus")
    missing = expected - set(verified)
    for entry in os.scandir(archive_documents):
        if (not missing or not entry.is_file(follow_symlinks=False)
                or HEX_SHA.fullmatch(entry.name.removesuffix(".json")) is None
                or not entry.name.endswith(".json") or entry.stat().st_size > MAX_RECEIPT_BYTES):
            continue
        raw = Path(entry.path).read_bytes()
        if not any(sha.encode() in raw for sha in missing):
            continue
        receipt = _read_receipt(Path(entry.path))
        sha = receipt.get("sha256")
        if sha not in missing:
            continue
        url = receipt.get("url")
        if not isinstance(url, str) or entry.name != hashlib.sha256(url.encode()).hexdigest() + ".json":
            raise ValueError("archive receipt identity not derived from source URL")
        _record(archive_documents, sha, url, receipt)
        _body_sha(documents, sha)
        references = receipt.get("references")
        if not isinstance(references, list) or not references:
            raise ValueError("archived source original has no original-row references")
        for ref in references:
            if not isinstance(ref, dict):
                raise TypeError("invalid source row reference")
            _archive_ref(archive_root, ref["source_url"], ref["source_sha256"],
                         ref["external_id"], ref["source_row"], url)
        verified[sha] = ("archive", hashlib.sha256(url.encode()).hexdigest())
        missing.remove(sha)
    if missing:
        raise ValueError("first-party original URL→source page→document provenance incomplete")
    keyed = "\n".join(f"{sha}:{kind}:{url_hash}" for sha, (kind, url_hash) in sorted(verified.items()))
    return {
        "status": "historical_first_party_source_lineage_verified",
        "original_sha256_count": len(verified),
        "primary_registry_source_count": sum(kind == "registry" for kind, _ in verified.values()),
        "historical_archive_category_source_count": sum(kind == "archive" for kind, _ in verified.values()),
        "historical_DP_matching_chunk_embeddings": sum(v["chunks"] for v in historic.values()),
        "proof_membership_aggregate_sha256": hashlib.sha256(keyed.encode()).hexdigest(),
        "live_source_current_status_verified": False,
        "live_DP_state_verified": False,
        "new_source_admission_authorized": False,
        "network_requests": 0,
        "db_mutations": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-snapshot", type=Path, required=True)
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    args = parser.parse_args()
    result = verify_saved_source_lineage(args.registry_snapshot, args.documents, args.archive_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
