from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path
from urllib.request import HTTPSHandler, ProxyHandler, build_opener

from src.shared.network.http_client import create_urllib_context
from src.tender_research.config import TenderResearchConfig
from src.tender_research.models import ProcurementTender
from src.tender_research.providers.ri223_rar_members import (
    Ri223RarError,
    extract_ri223_rar_members,
    is_ri223_rar_document,
)
from src.tender_research.repository import TenderRepository


def download_tender_documents(
    repo: TenderRepository,
    tender: ProcurementTender,
    config: TenderResearchConfig,
) -> dict[str, int]:
    tender_dir = _tender_doc_dir(config.data_dir, tender.source, tender.external_id)
    doc_dir = tender_dir / "documents" / "original"
    doc_dir.mkdir(parents=True, exist_ok=True)

    documents = tender.documents
    max_bytes = config.document_download_max_size_mb * 1024 * 1024
    downloaded = 0
    failed = 0
    expanded = 0
    for doc in list(documents):
        if doc.download_status == "downloaded":
            downloaded += 1
            expanded += _expand_source_bound_ri223_rar(repo, doc, doc_dir)
            continue
        if not doc.file_url:
            doc.download_status = "skipped"
            doc.error_message = "No file_url"
            repo._session.flush()
            continue
        local_path = doc_dir / _safe_filename(doc.file_name, doc.id)
        if local_path.exists():
            doc = _mark_downloaded(repo, doc, local_path)
            repo._session.flush()
            downloaded += 1
            expanded += _expand_source_bound_ri223_rar(repo, doc, doc_dir)
            continue
        try:
            req = urllib.request.Request(
                doc.file_url,
                headers={"User-Agent": "ArvectumTenderResearch/0.1"},
            )
            opener = _build_url_opener(doc.file_url, config)
            with opener.open(req, timeout=30) as resp:
                content = resp.read()
            if len(content) > max_bytes:
                doc.download_status = "skipped"
                doc.error_message = f"File too large: {len(content)} bytes"
                repo._session.flush()
                failed += 1
                continue
            local_path.write_bytes(content)
            doc = _mark_downloaded(repo, doc, local_path)
            repo._session.flush()
            downloaded += 1
            expanded += _expand_source_bound_ri223_rar(repo, doc, doc_dir)
        except Exception as e:  # noqa: BLE001 - isolated legacy downloader boundary
            doc.download_status = "failed"
            doc.error_message = str(e)
            repo._session.flush()
            failed += 1
    if expanded:
        # SQLAlchemy may have cached tender.documents before child insertion.
        repo._session.flush()
        repo._session.expire(tender, ["documents"])
    return {"downloaded": downloaded, "failed": failed}


def _expand_source_bound_ri223_rar(repo: TenderRepository, document, doc_dir: Path) -> int:
    if not is_ri223_rar_document(document) or not document.local_path:
        return 0
    evidence = document.raw_meta["evidence"]
    document.text_extraction_status = "unsupported"  # The container is never "extracted text".
    if document.raw_meta.get("rar_analysis", {}).get("status") == "CHILDREN_REGISTERED":
        return 0
    try:
        members = extract_ri223_rar_members(Path(document.local_path))
    except Ri223RarError as exc:
        document.raw_meta = {
            **document.raw_meta,
            "rar_analysis": {"status": "NEEDS_REVIEW", "reason": str(exc),
                             "content_analysis_complete": False},
        }
        repo._session.flush()
        return 0

    parent_sha256 = document.sha256 or hashlib.sha256(Path(document.local_path).read_bytes()).hexdigest()
    for member in members:
        member_hash = hashlib.sha256(member.content).hexdigest()
        path_hash = hashlib.sha256(member.path.encode("utf-8")).hexdigest()
        inner_stored = f"ri223-{parent_sha256[:12]}-{path_hash[:16]}{Path(member.filename).suffix.lower()}"
        local_path = doc_dir / inner_stored
        if local_path.is_file() and hashlib.sha256(local_path.read_bytes()).hexdigest() != member_hash:
            raise ValueError("Stored RI223 archive member changed content; reconciliation required")
        if not local_path.exists():
            local_path.write_bytes(member.content)
        repo.upsert_document({
            "tender_id": document.tender_id,
            "source_document_id": f"{document.source_document_id or document.id}/rar/{path_hash}",
            "file_name": member.filename,
            "file_url": None,
            "local_path": str(local_path),
            "size_bytes": len(member.content),
            "sha256": member_hash,
            "download_status": "downloaded",
            "text_extraction_status": "pending",
            "content_type": "application/octet-stream",
            "raw_meta": {
                "source_regime": "223fz",
                "source": "RI223_RAR_MEMBER",
                "parent_document_id": document.id,
                "parent_document_source_id": document.source_document_id,
                "parent_archive_sha256": parent_sha256,
                "archive_member": member.path,
                "evidence": evidence,
                "content_analysis_complete": False,
            },
        })
    document.raw_meta = {
        **document.raw_meta,
        "rar_analysis": {"status": "CHILDREN_REGISTERED",
                         "member_count": len(members),
                         "content_analysis_complete": False},
    }
    repo._session.flush()
    return len(members)


def _mark_downloaded(repo: TenderRepository, doc, path: Path):
    downloaded_doc = repo.upsert_document({
        "tender_id": doc.tender_id,
        "source_document_id": doc.source_document_id,
        "file_name": doc.file_name,
        "file_url": doc.file_url,
        "local_path": str(path),
        "content_type": doc.content_type,
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "download_status": "downloaded",
        "text_extraction_status": doc.text_extraction_status,
        "extracted_text_path": doc.extracted_text_path,
        "extracted_text_chars": doc.extracted_text_chars,
        "raw_meta": doc.raw_meta,
        "error_message": None,
    })
    return downloaded_doc


def _tender_doc_dir(base_data_dir: str, source: str, external_id: str) -> Path:
    return Path(base_data_dir) / "tenders" / source / _safe_dirname(external_id)


def _build_url_opener(url: str, config: TenderResearchConfig):
    ssl_ctx, should_bypass = create_urllib_context(url)
    if should_bypass:
        return build_opener(HTTPSHandler(context=ssl_ctx), ProxyHandler({}))
    return build_opener(HTTPSHandler(context=ssl_ctx))


def _safe_filename(name: str, fallback_id: str) -> str:
    name = name.replace(" ", "_")
    name = "".join(c for c in name if c.isalnum() or c in "._-")
    if not name:
        return fallback_id
    return name[:200]


def _safe_dirname(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in "_-")
    return safe[:100] or "unknown"
