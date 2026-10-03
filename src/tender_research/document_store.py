from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path
from urllib.request import HTTPSHandler, ProxyHandler, build_opener

from src.shared.network.http_client import create_urllib_context

from src.tender_research.config import TenderResearchConfig
from src.tender_research.document_text_extractor import extract_text
from src.tender_research.models import ProcurementTender
from src.tender_research.repository import TenderRepository


def download_tender_documents(
    repo: TenderRepository,
    tender: ProcurementTender,
    config: TenderResearchConfig,
) -> dict[str, int]:
    tender_dir = _tender_doc_dir(config.data_dir, tender.source, tender.external_id)
    doc_dir = tender_dir / "documents" / "original"
    text_dir = tender_dir / "documents" / "extracted_text"
    doc_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    documents = tender.documents
    max_bytes = config.document_download_max_size_mb * 1024 * 1024
    downloaded = 0
    failed = 0
    for doc in documents:
        if doc.download_status == "downloaded":
            downloaded += 1
            if doc.local_path and Path(doc.local_path).exists():
                _try_extract(doc, text_dir, config)
                repo._session.flush()
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
            _try_extract(doc, text_dir, config)
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
            _try_extract(doc, text_dir, config)
        except Exception as e:
            doc.download_status = "failed"
            doc.error_message = str(e)
            repo._session.flush()
            failed += 1
    return {"downloaded": downloaded, "failed": failed}


def _try_extract(doc, text_dir: Path, config: TenderResearchConfig) -> None:
    if doc.text_extraction_status == "extracted":
        return
    if not doc.local_path or not Path(doc.local_path).exists():
        return
    # Retry archive-backed EIS documents that were previously marked
    # unsupported/empty before ZIP container extraction was available.
    if (
        doc.text_extraction_status in ("unsupported", "empty")
        and Path(doc.local_path).suffix.lower() != ".zip"
    ):
        return
    status, text = extract_text(doc.local_path, max_chars=config.document_extract_max_chars)
    doc.text_extraction_status = status
    if status == "extracted" and text:
        text_path = text_dir / f"{_safe_filename(doc.file_name, doc.id)}.txt"
        text_path.write_text(text, encoding="utf-8")
        doc.extracted_text_path = str(text_path)
        doc.extracted_text_chars = len(text)
    elif status == "extracted":
        doc.extracted_text_chars = 0


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
