"""Narrow recovery evidence for public EIS 44-FZ DOCX and stored signed office ZIPs."""

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
from src.tender_research.rag.signed_zip import MAX_ENVELOPE, unwrap_signed_office


def digest(content):
    return hashlib.sha256(content).hexdigest()


def validate_docx(content):
    _validate_office(content, ".docx")


def _validate_office(content, extension):
    required = {".docx": "word/document.xml", ".xlsx": "xl/workbook.xml"}
    if extension not in required:
        raise ValueError("unsupported office member")
    if not 0 < len(content) <= MAX_ENVELOPE:
        raise ValueError("office source outside bounded size")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as package:
            entries = package.infolist()
            names = {x.filename for x in entries}
            if (
                len(entries) > 2048
                or len(names) != len(entries)
                or not {"[Content_Types].xml", required[extension]} <= names
                or sum(x.file_size for x in entries) > 100 * 1024**2
            ):
                raise ValueError("invalid office package")
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
                    raise ValueError("unsafe office member")
    except zipfile.BadZipFile as exc:
        raise ValueError("not an office package") from exc


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


def _signed_extension(name):
    return next((ext for ext in (".docx", ".xlsx") if name.lower().endswith(ext + ".zip")), None)


def _verified_original_evidence(document, folder):
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
    extension = _signed_extension(document.file_name)
    evidence = None
    if extension:
        member, evidence, _ = unwrap_signed_office(path, document.sha256, extension=extension)
        _validate_office(member, extension)
    else:
        validate_docx(content)
    return path, evidence


def verified_original(document, folder):
    return _verified_original_evidence(document, folder)[0]


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
            or not name.lower().endswith((".docx", ".docx.zip", ".xlsx.zip"))
            or not _official_url(link.url)
        ):
            raise ValueError("unsupported recovery original")
        identity = (str((link.raw or {}).get("uid") or link.url).casefold(), link.url, name)
        if _signed_extension(name):
            stored = [
                doc for doc in tender.documents
                if doc.source_document_id
                and (doc.source_document_id.casefold(), doc.file_url, doc.file_name) == identity
            ]
            if (
                len(stored) != 1 or stored[0].download_status != "downloaded"
                or not stored[0].local_path or not stored[0].sha256
                or type(stored[0].size_bytes) is not int
                or not 0 < stored[0].size_bytes <= MAX_ENVELOPE
            ):
                raise ValueError("signed ZIP recovery requires an existing downloaded original")
        links.append(identity)
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



def _verify_companion_projection(document, evidence, chunks, text):
    """Reject legacy single-member or inconsistent companion projections."""
    raw = document.raw_meta or {}
    if raw.get("signed_zip") != evidence:
        raise ValueError("signed ZIP projection evidence mismatch")
    expected = {
        evidence["member_sha256"]: (
            evidence["member_name"],
            f"tender-document://{document.id}/member/{evidence['member_sha256']}",
        ),
        evidence["pdf_companion"]["member_sha256"]: (
            evidence["pdf_companion"]["member_name"],
            f"tender-document://{document.id}/pdf-companion/{evidence['pdf_companion']['member_sha256']}",
        ),
    }
    receipts = (raw.get("data_platform_processing") or {}).get("metadata", {}).get("signed_office_members")
    if not isinstance(receipts, list) or len(receipts) != 2:
        raise ValueError("signed ZIP member receipts missing")
    indexed = {}
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise TypeError("signed ZIP member receipt mismatch")
        sha = receipt.get("member_sha256")
        if (
            sha not in expected or sha in indexed
            or (receipt.get("member_name"), receipt.get("canonical_uri")) != expected[sha]
            or any(not isinstance(receipt.get(k), str) or not receipt[k]
                   for k in ("resource_id", "document_id"))
        ):
            raise ValueError("signed ZIP member receipt mismatch")
        indexed[sha] = receipt
    if any(len({r[key] for r in receipts}) != 2 for key in ("resource_id", "document_id")):
        raise ValueError("signed ZIP member receipt collision")
    seen = set()
    for chunk in chunks:
        if (
            type(chunk.char_start) is not int or type(chunk.char_end) is not int
            or not 0 <= chunk.char_start < chunk.char_end <= len(text)
            or text[chunk.char_start:chunk.char_end].strip() != chunk.text
        ):
            raise ValueError("signed ZIP projection span mismatch")
        platform = chunk.raw_meta["data_platform"]
        refs = platform.get("archive_members")
        if not isinstance(refs, list) or not refs:
            raise ValueError("signed ZIP member references missing")
        for ref in refs:
            if not isinstance(ref, dict):
                raise TypeError("signed ZIP member reference mismatch")
            sha = ref.get("member_sha256")
            if (
                sha not in indexed
                or any(ref.get(k) != v for k, v in indexed[sha].items())
                or not isinstance(ref.get("chunk_id"), str) or not ref["chunk_id"]
                or ref.get("coordinate_space") != "normalized_member_text"
                or type(ref.get("char_start")) is not int
                or type(ref.get("char_end")) is not int
                or not 0 <= ref["char_start"] < ref["char_end"]
            ):
                raise ValueError("signed ZIP member reference mismatch")
            seen.add(sha)
        if any(platform.get(k) != refs[0].get(k) for k in ("resource_id", "document_id", "canonical_uri", "chunk_id")):
            raise ValueError("signed ZIP primary projection mismatch")
    if seen != set(expected):
        raise ValueError("signed ZIP member coverage incomplete")


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
            original, signed_evidence = _verified_original_evidence(d, folder)
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
                if signed_evidence is not None and signed_evidence.get("pdf_companion"):
                    _verify_companion_projection(d, signed_evidence, chunks, text)
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
