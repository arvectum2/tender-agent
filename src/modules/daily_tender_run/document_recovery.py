"""Narrow recovery evidence for existing public EIS 44-FZ DOCX inventories."""

from __future__ import annotations

import hashlib
import io
import os
import stat
import zipfile
from pathlib import Path
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from src.shared.network.http_client import create_urllib_context
from src.tender_research.rag.missing_attachments import _official_url
from src.tender_research.rag.signed_zip import MAX_ENVELOPE, unwrap_signed_docx


def digest(content):
    return hashlib.sha256(content).hexdigest()


def validate_docx(content):
    if not 0 < len(content) <= MAX_ENVELOPE:
        raise ValueError("DOCX source outside bounded size")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as package:
            entries = package.infolist()
            names = {x.filename for x in entries}
            if (
                len(entries) > 2048
                or len(names) != len(entries)
                or not {"[Content_Types].xml", "word/document.xml"} <= names
                or sum(x.file_size for x in entries) > 100 * 1024**2
            ):
                raise ValueError("invalid DOCX package")
            for x in entries:
                p = Path(x.filename)
                if (
                    p.is_absolute()
                    or ".." in p.parts
                    or "\\" in x.filename
                    or ":" in x.filename
                    or x.flag_bits & 1
                    or stat.S_IFMT(x.external_attr >> 16)
                    not in {0, stat.S_IFREG, stat.S_IFDIR}
                ):
                    raise ValueError("unsafe DOCX member")
    except zipfile.BadZipFile as exc:
        raise ValueError("not a DOCX package") from exc


class OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _official_url(newurl):
            raise ValueError("off-source document redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_docx(url, config):
    if not _official_url(url):
        raise ValueError("unbound official document URL")
    ssl_ctx, bypass = create_urllib_context(url)
    handlers = [HTTPSHandler(context=ssl_ctx), OfficialRedirect()]
    if bypass:
        handlers.append(ProxyHandler({}))
    limit = min(MAX_ENVELOPE, config.document_download_max_size_mb * 1024**2)
    with build_opener(*handlers).open(
        Request(url, headers={"User-Agent": "ArvectumTenderResearch/0.1"}), timeout=30
    ) as response:
        if not _official_url(response.geturl()):
            raise ValueError("unbound final document URL")
        content = response.read(limit + 1)
    if not 0 < len(content) <= limit:
        raise ValueError("document download size limit exceeded")
    validate_docx(content)
    return content


def verified_original(document, folder):
    if not document.local_path or not document.sha256:
        raise ValueError("missing original evidence")
    path = Path(document.local_path)
    if (
        path.is_symlink()
        or not path.is_file()
        or path.resolve().parent != folder
        or path.stat().st_size > MAX_ENVELOPE
    ):
        raise ValueError("unsafe stored original file")
    with path.open("rb") as stream:
        content = stream.read(MAX_ENVELOPE + 1)
    if len(content) != document.size_bytes or digest(content) != document.sha256:
        raise ValueError("original bytes disagree with registered evidence")
    if document.file_name.lower().endswith(".docx.zip"):
        member, _ = unwrap_signed_docx(path, document.sha256)
        validate_docx(member)
    else:
        validate_docx(content)
    return path


def save_original(folder, document, content):
    validate_docx(content)
    if (
        not document.file_name.lower().endswith(".docx")
        or document.local_path
        or document.sha256
    ):
        raise ValueError("not an empty DOCX destination")
    from uuid import UUID

    if str(UUID(str(document.id))) != str(document.id):
        raise ValueError("invalid document identity")
    folder.mkdir(parents=True, exist_ok=True)
    if folder.resolve() != folder or folder.is_symlink():
        raise ValueError("unsafe original directory")
    path = folder / (str(document.id) + ".docx")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return path, digest(content)


def source_inventory(tender, detail):
    revision = detail.active_revision
    selection = detail.raw.get("document_revision_selection") or {}
    if (
        tender.source != "eis"
        or tender.law_type != "44fz"
        or detail.registry_number != tender.registry_number
        or detail.law_type != "44fz"
        or detail.network_status != "success"
        or detail.raw.get("documents_fetch_status") != "success"
        or selection.get("status") != "active_revision_selected"
        or selection.get("requires_review") is not False
        or not revision
        or revision.active is not True
        or not isinstance(revision.revision, int)
        or revision.revision <= 0
        or not revision.publication_timestamp
        or not revision.source_url
        or not _official_url(revision.source_url, registry=tender.registry_number)
        or not detail.documents_html
        or detail.document_links != revision.document_links
        or not 1 <= len(detail.document_links) <= 10
    ):
        raise ValueError("active source revision not proven")
    links = []
    for link in detail.document_links:
        name = link.file_name or link.title
        if (
            not name
            or not name.lower().endswith((".docx", ".docx.zip"))
            or not _official_url(link.url)
        ):
            raise ValueError("unsupported recovery original")
        links.append(
            (str((link.raw or {}).get("uid") or link.url).casefold(), link.url, name)
        )
    if len({x[0] for x in links}) != len(links):
        raise ValueError("duplicate source attachment ID")
    revision_identity = (
        revision.revision,
        revision.publication_timestamp,
        revision.source_url,
    )
    if tender.documents:
        existing = []
        for doc in tender.documents:
            meta = doc.raw_meta or {}
            r = meta if meta.get("documents_html_sha256") else meta.get("raw") or {}
            if (
                (
                    r.get("revision"),
                    r.get("revision_publication_timestamp"),
                    r.get("revision_source_url"),
                )
                != revision_identity
                or not doc.source_document_id
                or not doc.file_url
            ):
                raise ValueError("stored document revision differs")
            existing.append(
                (doc.source_document_id.casefold(), doc.file_url, doc.file_name)
            )
        if sorted(existing) != sorted(links):
            raise ValueError("stored inventory differs from current source")
    return {"revision": list(revision_identity), "links": sorted(links)}


def next_document_stage(repo, tender, folder):
    """Check all persisted originals; pick one deterministic incomplete document."""
    if not tender.documents:
        if repo.count_chunks_by_tender(tender.id):
            raise ValueError("empty inventory with unexpected chunks")
        return "register_inventory", None, []
    evidence = []
    pending = []
    for d in sorted(tender.documents, key=lambda x: str(x.id)):
        chunks = repo.list_document_chunks(d.id)
        if d.download_status != "downloaded":
            if (
                d.download_status not in {"pending", "failed"}
                or chunks
                or d.local_path
                or d.sha256
                or not d.file_name.lower().endswith(".docx")
            ):
                raise ValueError("unexpected pending document state")
            if (folder / (str(d.id) + ".docx")).exists():
                raise ValueError("unreconciled original destination")
            stage = "download_document"
        else:
            original = verified_original(d, folder)
            if d.text_extraction_status == "extracted":
                if not d.extracted_text_path or not chunks:
                    raise ValueError("incomplete extracted document")
                p = Path(d.extracted_text_path)
                if (
                    p.is_symlink()
                    or not p.is_file()
                    or p.resolve().parent != folder.parent / "extracted_text"
                    or p.stat().st_size > 8 * 1024**2
                ):
                    raise ValueError("unsafe extracted document path")
                text = p.read_text(encoding="utf-8")
                if len(text) != d.extracted_text_chars:
                    raise ValueError("extracted text length mismatch")
                if (d.raw_meta or {}).get("data_platform_processing", {}).get(
                    "ocr_review", {}
                ).get("requires_review") is not False:
                    raise ValueError("extracted evidence needs review")
                for c in chunks:
                    meta = c.raw_meta or {}
                    if (
                        meta.get("source") != "data_platform_projection"
                        or not meta.get("data_platform", {}).get("chunk_id")
                        or c.document_id != d.id
                        or digest(c.text.encode()) != c.text_hash
                    ):
                        raise ValueError("projection chunk evidence mismatch")
                stage = "complete"
            else:
                if (
                    chunks
                    or d.extracted_text_path
                    or d.text_extraction_status
                    not in {"pending", "unsupported", "failed"}
                ):
                    raise ValueError("unreconciled projection")
                if (original.parent.parent / "extracted_text" / f"{d.id}.txt").exists():
                    raise ValueError("unreconciled extracted text destination")
                stage = "project_document"
        evidence.append(
            {
                "id": str(d.id),
                "state": stage,
                "original_sha256": d.sha256,
                "chunks": sorted((str(c.id), c.text_hash) for c in chunks),
            }
        )
        if stage != "complete":
            pending.append((stage, d))
    if pending:
        stage, doc = pending[0]
        return stage, doc, evidence
    return "ensure_collection", None, evidence
