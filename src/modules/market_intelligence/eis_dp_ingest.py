"""MI-012: source-verified EIS documents -> existing tenant-scoped Data Platform.

Call only from an authenticated Tender Agent service. Never grant consumer
access on the basis of client-supplied receipt data. No network in dry-run.
"""

from __future__ import annotations

import hashlib
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .eis_source_ledger import extract_archive
from .portfolio_pipeline import _slug

SHA = re.compile(r"[0-9a-f]{64}\Z")
NUMBER = re.compile(r"(?:[0-9]{11}|[0-9]{19,20})\Z")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,180}\Z")
FORMATS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".pptx", ".rtf", ".txt"}
MIME = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".rtf": "application/rtf",
    ".txt": "text/plain",
}
MAX_DOCUMENTS = 24
MAX_SINGLE_FILE = 20 * 1024 * 1024
MAX_TOTAL = 96 * 1024 * 1024
MAX_PARENT_ZIP = 160 * 1024 * 1024


class EISIndexError(ValueError):
    """Unsafe source, invalid identity, or unverified Data Platform result."""


class DataPlatformIngest(Protocol):
    def ensure_collection(self, *, collection_id: str, name: str, owner: str,
                          default_language: str = "russian",
                          access_policy: dict[str, Any] | None = None) -> dict[str, Any]: ...
    def ingest_document_bytes(self, *, collection_id: str, canonical_uri: str,
                              title: str, content: bytes, filename: str,
                              content_type: str = "application/octet-stream",
                              pre_chunked: bool = False) -> dict[str, Any]: ...


@dataclass(frozen=True)
class TrustedTenant:
    """Must be built from validated session and server-side ACL, not input JSON."""

    tenant_id: str
    consumer_id: str
    authorized_collection_ids: frozenset[str]


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise EISIndexError(f"{label}: lowercase SHA-256 required")
    return value


def _verify_nested_original(root: Path, row: dict[str, Any], expected_child: str) -> None:
    """Check the parent ZIP and original member, not just the staged child."""
    name = row["parent_zip_name"]
    if not isinstance(name, str) or not NAME.fullmatch(name) or not name.endswith(".zip"):
        raise EISIndexError("Invalid original ZIP filename")
    if root.is_symlink() or not root.is_dir():
        raise EISIndexError("Original ZIP directory missing or symlinked")
    parent = root / name
    if parent.is_symlink() or not parent.is_file():
        raise EISIndexError("Original ZIP parent unavailable")
    if not 0 < parent.stat().st_size <= MAX_PARENT_ZIP:
        raise EISIndexError("Original ZIP exceeds source size limit")
    digest = hashlib.sha256()
    with parent.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != row["parent_zip_sha"]:
        raise EISIndexError("Original ZIP SHA mismatch")
    try:
        with zipfile.ZipFile(parent) as archive:
            infos = archive.infolist()
            if len(infos) > 300:
                raise EISIndexError("Original ZIP has too many members")
            matches = [
                info for info in infos
                if hashlib.sha256(info.filename.encode()).hexdigest()
                == row["original_member_path_sha256"]
            ]
            if len(matches) != 1:
                raise EISIndexError("Original ZIP member locator not unique")
            member = matches[0]
            if (
                member.is_dir() or member.flag_bits & 1
                or stat.S_ISLNK(member.external_attr >> 16)
                or member.file_size > MAX_SINGLE_FILE
                or (member.file_size and not member.compress_size)
                or (member.compress_size > 0 and member.file_size > member.compress_size * 250)
            ):
                raise EISIndexError("Unsafe compressed original ZIP member")
            size = 0
            digest = hashlib.sha256()
            with archive.open(member, "r") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    size += len(block)
                    if size > MAX_SINGLE_FILE:
                        raise EISIndexError("ZIP member exceeds upload byte budget")
                    digest.update(block)
            if size != member.file_size or digest.hexdigest() != expected_child:
                raise EISIndexError("Staged child differs from original ZIP")
    except (zipfile.BadZipFile, OSError) as exc:
        raise EISIndexError("Original ZIP unreadable") from exc


def procurement_collection(tenant: str, run: str) -> str:
    tenant = _slug(tenant, "tenant_id")
    run = _slug(run, "run_id")
    digest = hashlib.sha256((tenant + "/" + run).encode()).hexdigest()
    return "mi-eis-" + digest[:32]


def _read_source(root: Path, relative_folder: str, name: Any, digest: str) -> bytes:
    if relative_folder not in ("", "source_bound_zip_children"):
        raise EISIndexError("Unapproved original document directory")
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise EISIndexError("Untrusted file name")
    if root.is_symlink() or not root.is_dir():
        raise EISIndexError("Source root unavailable/symlinked")
    parent = root / relative_folder if relative_folder else root
    if parent.is_symlink() or not parent.is_dir():
        raise EISIndexError("Source child folder unavailable/symlinked")
    path = parent / name
    if path.is_symlink() or not path.is_file():
        raise EISIndexError("Original document missing or symlinked")
    size = path.stat().st_size
    if not 0 < size <= MAX_SINGLE_FILE:
        raise EISIndexError("Original document exceeds upload limit")
    with path.open("rb") as f:
        data = f.read(MAX_SINGLE_FILE + 1)
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise EISIndexError("Original document SHA-256 mismatch")
    return data


def _candidates(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    if receipt.get("status") != "downloaded":
        raise EISIndexError("Original EIS download receipt not successful")
    rows = receipt.get("records")
    if not isinstance(rows, list) or len(rows) > MAX_DOCUMENTS:
        raise EISIndexError("Original download receipt count out of bounds")
    candidates: list[dict[str, Any]] = []
    number = receipt["registry_number"]
    for row in rows:
        if not isinstance(row, dict):
            raise EISIndexError("Malformed EIS attachment record")
        if row.get("status") != "saved":
            continue
        archive_sha = _sha(row.get("original_archive_sha256"), "ZIP SHA")
        xml_sha = _sha(row.get("source_xml_sha256"), "XML SHA")
        content_sha = _sha(row.get("document_sha256") or row.get("file_sha256"), "file SHA")
        url_sha = _sha(row.get("source_url_sha256") or row.get("official_url_sha256"), "official URL SHA")
        extension = row.get("extension")
        if extension in FORMATS:
            candidates.append({
                "name": row.get("stored_name"), "subdir": "", "extension": extension,
                "archive_sha": archive_sha, "xml_sha": xml_sha, "sha": content_sha,
                "url_sha": url_sha, "number": number,
                "revision_review": bool(row.get("revision_requires_review")),
                "source_kind": "native",
            })
        children = row.get("zip_children")
        if children is not None:
            if (not isinstance(children, dict)
                    or children.get("schema_version") != "mi-eis-official-zip-children/0.1"
                    or children.get("original_parent_zip_sha256") != content_sha):
                raise EISIndexError("Original ZIP children lack valid parent provenance")
            child_rows = children.get("records")
            if not isinstance(child_rows, list) or len(child_rows) > MAX_DOCUMENTS:
                raise EISIndexError("Original ZIP child count out of bounds")
            for child in child_rows:
                if not isinstance(child, dict):
                    raise EISIndexError("Malformed ZIP child record")
                if child.get("status") != "staged_sha256_verified_not_yet_indexed":
                    continue
                ext = child.get("member_extension")
                if ext not in FORMATS or child.get("original_parent_zip_sha256") != content_sha:
                    raise EISIndexError("Unsupported original ZIP member or parent SHA mismatch")
                candidates.append({
                    "name": child.get("local_stored_name"),
                    "subdir": "source_bound_zip_children", "extension": ext,
                    "archive_sha": archive_sha, "xml_sha": xml_sha,
                    "sha": _sha(child.get("member_sha256"), "ZIP child SHA"),
                    "url_sha": url_sha, "number": number,
                    "revision_review": bool(row.get("revision_requires_review")),
                    "source_kind": "zip_member",
                    "parent_zip_name": row.get("stored_name"),
                    "parent_zip_sha": content_sha,
                    "original_member_path_sha256": _sha(child.get("original_member_path_sha256"), "original member path SHA"),
                })
    if not candidates or len(candidates) > MAX_DOCUMENTS:
        raise EISIndexError("No supported bounded original document candidates")
    return candidates


def ingest_original_eis_documents(
    client: DataPlatformIngest | None, *,
    receipt: dict[str, Any],
    source_archive: Path, original_archive_sha256: str,
    source_region: str, source_date: str, subsystem: str,
    original_files_dir: Path,
    trusted: TrustedTenant, tenant_id: str, run_id: str,
    execute: bool = False, allow_unreviewed_revisions: bool = False,
) -> dict[str, Any]:
    """Verify ALL byte and tenant evidence before any DP write.

    TrustedTenant values must come from server-authenticated policy.
    Dry-run defaults to zero Data Platform network calls.
    """
    tenant = _slug(tenant_id, "tenant_id")
    consumer = _slug(trusted.consumer_id, "consumer_id")
    if tenant != _slug(trusted.tenant_id, "authenticated_tenant_id"):
        raise EISIndexError("Cross-tenant request denied")
    collection_id = procurement_collection(tenant, run_id)
    if collection_id not in trusted.authorized_collection_ids:
        raise EISIndexError("No authenticated collection authorization")
    number = receipt.get("registry_number")
    if not isinstance(number, str) or not NUMBER.fullmatch(number):
        raise EISIndexError("Unrecognized official procurement number")
    if (subsystem, len(number)) not in (("RI223", 11), ("PRIZ", 19), ("PRIZ", 20)):
        raise EISIndexError("Original procurement law/number mismatch")
    archive_sha = _sha(original_archive_sha256, "original EIS source archive")
    original_xml = extract_archive(
        source_archive, official_archive_sha256=archive_sha,
        subsystem=subsystem, region=source_region, exact_date=source_date,
    )
    official_xml_hashes = {
        row["source"]["xml_sha256"] for row in original_xml
        if row["record_kind"] == "notice" and row.get("notice_number") == number
    }
    if not official_xml_hashes:
        raise EISIndexError("Official ZIP does not prove matching procurement notice")
    rows = _candidates(receipt)
    data_to_ingest = []
    total = 0
    seen = set()
    for row in rows:
        if row["archive_sha"] != archive_sha or row["xml_sha"] not in official_xml_hashes:
            raise EISIndexError("Downloaded file not bound to exact original EIS XML/ZIP")
        if row["revision_review"] and not allow_unreviewed_revisions:
            raise EISIndexError("Document revision requires explicit source review")
        if not isinstance(row["name"], str) or not row["name"].endswith(row["extension"]):
            raise EISIndexError("Original saved file name and extension mismatch")
        if row["source_kind"] == "zip_member":
            _verify_nested_original(original_files_dir, row, row["sha"])
        data = _read_source(
            original_files_dir, row["subdir"], row["name"], row["sha"],
        )
        total += len(data)
        if total > MAX_TOTAL:
            raise EISIndexError("Original document batch exceeds 96MiB")
        uri = f"mi-eis://{collection_id}/{number}/sha256/{row['sha']}"
        if uri in seen:
            continue
        seen.add(uri)
        data_to_ingest.append((row, data, uri))
    result = {
        "schema_version": "mi-eis-dp-original-ingest/0.1",
        "collection_id": collection_id,
        "tenant_id": tenant,
        "registry_number": number,
        "validated_documents": len(data_to_ingest),
        "source_archive_sha256": archive_sha,
        "prevalidated_source_bytes": True,
        "indexing_executed": False,
        "revision_requires_review": any(x[0]["revision_review"] for x in data_to_ingest),
        "winner_verified": False,
        "signed_contract_price_verified": False,
        "documents": [
            {
                "canonical_uri": uri, "source_binary_sha256": row["sha"],
                "source_xml_sha256": row["xml_sha"],
                "source_kind": row["source_kind"], "extension": row["extension"],
                "bytes": len(data), "index_status": "verified_not_indexed",
            }
            for row, data, uri in data_to_ingest
        ],
    }
    if not execute:
        return result
    if client is None:
        raise EISIndexError("Authenticated Data Platform SDK client required")
    policy = {"tenant_id": tenant, "allowed_consumers": [consumer]}
    collection = client.ensure_collection(
        collection_id=collection_id, name=f"EIS originals {run_id}",
        owner=f"market-intelligence:{tenant}", default_language="russian",
        access_policy=policy,
    )
    if (
        not isinstance(collection, dict)
        or collection.get("collection_id") != collection_id
        or collection.get("owner") != f"market-intelligence:{tenant}"
        or collection.get("access_policy") != policy
    ):
        raise EISIndexError("Data Platform collection owner/tenant ACL mismatch")
    for index, (row, data, uri) in enumerate(data_to_ingest):
        outcome = client.ingest_document_bytes(
            collection_id=collection_id, canonical_uri=uri,
            title=f"EIS {number}: original file {index+1}",
            content=data, filename=row["name"], content_type=MIME[row["extension"]],
            pre_chunked=False,
        )
        if (
            not isinstance(outcome, dict)
            or outcome.get("collection_id") != collection_id
            or outcome.get("canonical_uri") not in (None, uri)
            or outcome.get("extraction_status") != "extracted"
            or not outcome.get("document_id")
        ):
            raise EISIndexError("Data Platform extraction/indexing failed; partial writes may need review")
        result["documents"][index].update({
            "index_status": "ingested_extracted",
            "document_id": outcome["document_id"],
            "resource_id": outcome.get("resource_id"),
        })
    result["indexing_executed"] = True
    return result
