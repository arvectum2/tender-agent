"""Source-SHA-bound official EIS 44-FZ docs for Tender Research & Data Platform.

Owner-private source ZIP (already in the canonical learning corpus) is the only
original accepted here. The exact archived epNotification XML identifies each
official filestore URL. Download all file bytes and validate before any writes.

A notice/ZIP SHA is an archive snapshot, NOT a verified current legal EIS
status or e-signature; no public response or bidder decision can be inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from scripts.acceptance.audit_eis_oct18_original_attachments import (
    magic_match,
    official_filestore,
)
from scripts.procurement_llm.analysis_queue_worker import (
    PinnedSource,
    attest_source,
    source_rows,
)
from scripts.procurement_llm.collect_eis_official_archives import classify_archive
from scripts.procurement_llm.collect_public_market_originals import OWNER_PRIVATE
from scripts.procurement_llm.import_candidates import _engine_url
from scripts.procurement_llm.source_pipeline_runtime import (
    fresh_pg_backup,
    single_runner,
)
from src.modules.tender_operator_agent_demo.eis_notice_parser import (
    extract_notice_attachments,
    extract_notice_metadata,
)
from src.modules.tender_operator_agent_demo.settings import get_zakupki_soap_settings
from src.modules.tender_operator_agent_demo.zakupki_soap_client import ZakupkiSoapClient
from src.tender_research.repository import TenderRepository

NUMBER = re.compile(r"[0-9]{19}\Z")
MAX_XML = 2_000_000
MAX_FILES = 25
MAX_BINARY = 10_000_000
MAX_TOTAL = 35_000_000
TITLE_TAGS = {"purchaseObjectInfo", "purchaseName"}
SAFE_FORMAT = {".docx", ".pdf", ".doc", ".xls", ".xlsx", ".zip"}


class SourcePreparationError(ValueError):
    """Exact official source bytes or versioned document preparation invalid."""


@dataclass(frozen=True)
class SourceDocument:
    name: str
    source_url_sha256: str
    original_url: str  # Never serialize to the saved report or DB.
    role: str
    data: bytes
    sha256: str
    extension: str
    kind: str


def _digest(binary: bytes) -> str:
    return hashlib.sha256(binary).hexdigest()


def _safe_name(name: object) -> str:
    if (
        not isinstance(name, str) or not 1 <= len(name) <= 230
        or any(char in name for char in ("/", "\\", "\x00"))
        or name in {".", ".."}
        or Path(name).suffix.lower() not in SAFE_FORMAT
    ):
        raise SourcePreparationError("unexpected source attachment name or format")
    return name


def _selected_notice(src: PinnedSource) -> tuple[bytes, dict]:
    if src.platform != "eis" or not NUMBER.fullmatch(src.procurement_ref):
        raise SourcePreparationError("only canonical 44-FZ EIS archived original accepted")
    original = src.path.read_bytes()
    classified = classify_archive(src.procurement_ref, original)
    if classified["status"] != "ATTESTED_COMPETITIVE":
        raise SourcePreparationError("noncompetitive/ambiguous EIS original")
    version = classified["source_version"]
    match_name = re.compile(
        r"epNotification(?:EF2020|EZK2020|EOK2020)_"
        + re.escape(src.procurement_ref) + "_" + str(version)
        + r"_[0-9A-Fa-f]{32}\.xml\Z"
    )
    with zipfile.ZipFile(src.path) as zipped:
        members = [
            info for info in zipped.infolist()
            if not info.is_dir() and match_name.fullmatch(info.filename)
            and 0 < info.file_size <= MAX_XML
        ]
        if len(members) != 1:
            raise SourcePreparationError("selected versioned notice XML ambiguous")
        xml = zipped.read(members[0])
    if _digest(xml) != classified["notice_xml_sha256"]:
        raise SourcePreparationError("selected XML SHA differs from official ZIP receipt")
    if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise SourcePreparationError("XML entity declaration forbidden")
    return xml, classified


def _title_from_original(xml: bytes) -> str:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise SourcePreparationError("original notice XML unparseable") from exc
    matches = []
    for node in root.iter():
        name = node.tag.rsplit("}", 1)[-1]
        text = " ".join((node.text or "").split())
        if name in TITLE_TAGS and 15 <= len(text) <= 700 and text not in matches:
            matches.append(text)
    if len(matches) != 1:
        raise SourcePreparationError("original notice title missing/ambiguous")
    return matches[0]


def _snapshot(src: PinnedSource, *, fetch) -> tuple[dict, list[SourceDocument]]:
    xml, facts = _selected_notice(src)
    refs = extract_notice_attachments(xml.decode("utf-8-sig"))
    if not 1 <= len(refs) <= MAX_FILES:
        raise SourcePreparationError("unbounded/empty official notice attachment list")
    title = _title_from_original(xml)
    metadata = extract_notice_metadata(xml.decode("utf-8-sig"))
    documents = []
    seen = set()
    total = 0
    for item in refs:
        url = item["url"]
        name = _safe_name(item["name"])
        if (
            not isinstance(url, str) or not official_filestore(url)
            or url in seen
        ):
            raise SourcePreparationError("EIS filestore URL absent/duplicate/outside allowlist")
        seen.add(url)
        data = fetch(url)
        if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BINARY:
            raise SourcePreparationError("filestore returned no bounded original binary")
        total += len(data)
        if total > MAX_TOTAL:
            raise SourcePreparationError("filestore total source evidence oversized")
        try:
            kind = magic_match(name, data)
        except Exception as exc:
            raise SourcePreparationError("attachment binary format differs from XML name") from exc
        documents.append(SourceDocument(
            name=name, source_url_sha256=_digest(url.encode()),
            original_url=url, role=item.get("document_kind") or "attachment",
            data=data, sha256=_digest(data),
            extension=Path(name).suffix.lower(), kind=kind,
        ))
    manifest = {
        "schema": "arvectum_original_eis_source_documents_v1",
        "purchase_number": src.procurement_ref,
        "source_observation_id": src.observation_id,
        "archived_original_zip_sha256": src.original_sha256,
        "selected_notice_xml_sha256": facts["notice_xml_sha256"],
        "selected_notice_source_version": facts["source_version"],
        "notice_type": facts["notice_type"],
        "title_original": title,
        "customer_name_original": metadata.get("customer_name"),
        "nmck_original": metadata.get("nmck"),
        "complete_xml_linked_attachment_count": len(documents),
        "bytes_downloaded": total,
        "attachments": [
            {
                "source_index": i,
                "original_name": doc.name,
                "source_url_sha256": doc.source_url_sha256,
                "source_role_hint": doc.role,
                "original_binary_sha256": doc.sha256,
                "original_binary_size": len(doc.data),
                "binary_type": doc.kind,
                "opaque_unread_content": doc.kind != "DOCX_MAIN_BODY_OK",
                "source_current_live_status_verified": False,
            }
            for i, doc in enumerate(documents, 1)
        ],
        "all_original_binaries_saved": False,
        "source_current_live_status_verified": False,
        "eis_xml_signature_cryptographically_verified": False,
        "owner_legal_bid_go": False,
        "human_training_gold": False,
    }
    return manifest, documents


def real_filestore_fetch(url: str) -> bytes:
    # Existing official transport respects direct RU route and byte cap. No
    # signed URL query is ever logged or retained after this in-memory fetch.
    settings = get_zakupki_soap_settings()
    if not (settings.configured and settings.disable_proxy_for_eis
            and settings.require_direct_ru_route):
        raise SourcePreparationError("official direct EIS filestore not configured")
    if not official_filestore(url):
        raise SourcePreparationError("untrusted EIS filestore URL")
    client = ZakupkiSoapClient(settings, runtime_status_enabled=False)
    try:
        data, _ = client._http_get(
            url, headers={"User-Agent": settings.user_agent},
            timeout=25, max_bytes=MAX_BINARY,
        )
    except Exception as exc:
        raise SourcePreparationError("official EIS filestore original unavailable") from exc
    return data


def _private_dir(root: Path, number: str, sha: str) -> Path:
    if root.is_symlink() or not root.is_dir():
        raise SourcePreparationError("private ArvectumSSD root inaccessible")
    dest = root / "eis-source-documents" / number / sha
    for folder in (root / "eis-source-documents",
                   root / "eis-source-documents" / number, dest):
        if folder.is_symlink():
            raise SourcePreparationError("original documents symlink ancestor")
        folder.mkdir(exist_ok=True, mode=0o700)
        if stat.S_IMODE(folder.stat().st_mode) & 0o077:
            raise SourcePreparationError("original directory access too permissive")
    return dest


def _preserve(path: Path, blob: bytes) -> bool:
    if path.is_symlink():
        raise SourcePreparationError("unsafe original document symlink")
    sha = _digest(blob)
    # Indexed document paths may include an ordinal for collision safety.
    if path.name != sha + path.suffix and not re.fullmatch(
        r"[0-9]{2}-" + sha + re.escape(path.suffix), path.name
    ):
        raise SourcePreparationError("unexpected original document SHA path")
    if path.exists():
        if (
            not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600
            or _digest(path.read_bytes()) != sha
        ):
            raise SourcePreparationError("immutable original document mismatch")
        return False
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return True


def _attach_paths(manifest: dict, docs: list[SourceDocument], root: Path) -> tuple[dict, list[Path]]:
    out = dict(manifest)
    folder = _private_dir(root, manifest["purchase_number"],
                          manifest["archived_original_zip_sha256"])
    saved = []
    try:
        rows = []
        for index, doc in enumerate(docs, 1):
            path = folder / (f"{index:02d}-" + doc.sha256 + doc.extension)
            if _preserve(path, doc.data):
                saved.append(path)
            rows.append({**manifest["attachments"][index - 1],
                         "owner_private_original_path": str(path)})
        out["attachments"] = rows
        out["all_original_binaries_saved"] = True
        output = json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2).encode()
        manifest_path = folder / "source-manifest.json"
        if manifest_path.is_symlink():
            raise SourcePreparationError("manifest symlink")
        if manifest_path.exists():
            if manifest_path.read_bytes() != output or stat.S_IMODE(
                manifest_path.stat().st_mode
            ) != 0o600:
                raise SourcePreparationError("immutable source-manifest collision")
        elif _preserve_manifest(manifest_path, output):
            saved.append(manifest_path)
        return out, saved
    except BaseException:
        for path in saved:
            path.unlink(missing_ok=True)
        raise


def _preserve_manifest(path: Path, content: bytes) -> bool:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return True


def register_with_tender_research(session: Session, manifest: dict) -> dict:
    """Only local owner-original evidence, no signed URLs or legal status claims."""
    if manifest["all_original_binaries_saved"] is not True:
        raise SourcePreparationError("not all original files privately saved")
    entries = manifest["attachments"]
    for row in entries:
        path = Path(row["owner_private_original_path"])
        if (
            path.is_symlink() or not path.is_file()
            or stat.S_IMODE(path.stat().st_mode) != 0o600
            or _digest(path.read_bytes()) != row["original_binary_sha256"]
        ):
            raise SourcePreparationError("document original content changed before SQL")
    repo = TenderRepository(session)
    number = manifest["purchase_number"]
    existing = repo.get_tender_by_registry_number(number)
    if existing is not None:
        bound = (existing.raw_payload or {}).get(
            "owner_attested_original_archive_sha256"
        )
        if bound != manifest["archived_original_zip_sha256"]:
            raise SourcePreparationError("existing tender has different/unverified original binding")
    source_payload = {
        "owner_attested_original_archive_sha256": manifest["archived_original_zip_sha256"],
        "archived_notice_xml_sha256": manifest["selected_notice_xml_sha256"],
        "archived_notice_version": manifest["selected_notice_source_version"],
        "source_observation_id": manifest["source_observation_id"],
        "archived_original_file_manifest_sha256": _digest(json.dumps(
            manifest, ensure_ascii=False, sort_keys=True
        ).encode()),
        "complete_archived_filestore_file_count": len(entries),
        "all_original_downloaded": True,
        "live_eis_status_verified": False,
        "owner_bid_go": False,
    }
    tender = repo.upsert_tender({
        "source": "eis", "external_id": number, "registry_number": number,
        "law_type": "44fz", "title": manifest["title_original"],
        "customer_name": manifest["customer_name_original"],
        "nmck_amount": manifest["nmck_original"],
        "currency": "RUB",
        "status": "archived_original_only_no_live_status",
        "raw_payload": source_payload,
    })
    for idx, doc in enumerate(entries, 1):
        # .zip and .doc are source evidence, not extractable docx text by fiat.
        opaque = doc["opaque_unread_content"]
        repo.upsert_document({
            "tender_id": tender.id,
            "source_document_id": f"eis-archived-v{manifest['selected_notice_source_version']}-{idx:02d}",
            "file_name": doc["original_name"],
            "file_url": None,
            "local_path": doc["owner_private_original_path"],
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if not opaque else "application/octet-stream",
            "size_bytes": doc["original_binary_size"],
            "sha256": doc["original_binary_sha256"],
            "download_status": "downloaded" if not opaque else "registered_opaque",
            "text_extraction_status": "pending" if not opaque else "unsupported",
            "raw_meta": {
                "source": "EIS_GETDOCSIP_PINNED_XML_FILESTORE",
                "document_kind": doc["source_role_hint"],
                "source_document_index": idx,
                "source_archive_sha256": manifest["archived_original_zip_sha256"],
                "source_xml_sha256": manifest["selected_notice_xml_sha256"],
                "source_version": manifest["selected_notice_source_version"],
                "binary_sha256": doc["original_binary_sha256"],
                "source_url_sha256": doc["source_url_sha256"],
                "content_semantics_verified": not opaque,
                "eis_live_status_verified": False,
            },
        })
    session.flush()
    return {"tender_id": tender.id, "registered_original_documents": len(entries),
            "extractable_docx_count": sum(not x["opaque_unread_content"] for x in entries)}


def prepare(number: str, *, root: Path = OWNER_PRIVATE,
            fetch=real_filestore_fetch, apply=False,
            engine_factory=None) -> dict:
    if not isinstance(number, str) or not NUMBER.fullmatch(number):
        raise SourcePreparationError("explicit 19-digit EIS number required")
    engine = (engine_factory or (lambda: create_engine(_engine_url())))()
    try:
        with Session(engine) as session:
            sources = [x for x in source_rows(session)
                       if x.platform == "eis" and x.procurement_ref == number]
            session.rollback()
            if len(sources) != 1:
                raise SourcePreparationError("exact canonical owner EIS source not stored")
            src = sources[0]
            attest_source(src, root=root)
            manifest, docs = _snapshot(src, fetch=fetch)
            if not apply:
                return {
                    "mode": "no_write_verified_original_preparation",
                    "source_document_count": len(docs),
                    "official_attachments_verified_sha": len(docs),
                    "opaque_unread_count": sum(x.kind != "DOCX_MAIN_BODY_OK" for x in docs),
                    "source_original_archive_sha256": src.original_sha256,
                    "db_writes": 0,
                    "private_writes": 0,
                    "actual_llm_inference": False,
                }
            # Backup is called by our owner CLI after all remote files have
            # been verified, and before any source-file/DB mutation.
            saved_manifest, new_paths = _attach_paths(manifest, docs, root)
            try:
                with session.begin():
                    registered = register_with_tender_research(session, saved_manifest)
            except BaseException:
                for path in new_paths:
                    path.unlink(missing_ok=True)
                raise
            return {
                "mode": "canonical_source_bound_originals_registered",
                "number": number,
                "source_archive_sha256": src.original_sha256,
                "source_xml_sha256": manifest["selected_notice_xml_sha256"],
                "version": manifest["selected_notice_source_version"],
                "files_verified": len(docs),
                "opaque_unread_count": sum(x.kind != "DOCX_MAIN_BODY_OK" for x in docs),
                "new_private_files": len(new_paths),
                "db_registered": registered,
                "source_current_live_status_verified": False,
                "actual_llm_inference": False,
            }
    finally:
        engine.dispose()



def verify_registered_exact_source_set(
    session: Session, number: str, *, root: Path = OWNER_PRIVATE,
) -> dict:
    """Reread canonical source ZIP/XML and ALL original files before indexing.

    No network, no SQL or filesystem mutations. Refuse a forged source SHA in
    tender.raw_payload, stale XML version, changed attachment bytes or mismatch
    between the manifest and the existing registered Tender Research docs.
    """
    sources = [
        item for item in source_rows(session)
        if item.platform == "eis" and item.procurement_ref == number
    ]
    if len(sources) != 1:
        raise SourcePreparationError("registered exact original not in canonical corpus")
    src = sources[0]
    attest_source(src, root=root)
    xml, classified = _selected_notice(src)
    refs = extract_notice_attachments(xml.decode("utf-8-sig"))
    path = root / "eis-source-documents" / number / src.original_sha256 / "source-manifest.json"
    if (
        path.is_symlink() or not path.is_file()
        or stat.S_IMODE(path.stat().st_mode) != 0o600
        or not path.resolve().is_relative_to(root.resolve())
        or not 0 < path.stat().st_size <= 100_000
    ):
        raise SourcePreparationError("original manifest missing/unsafe")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise SourcePreparationError("original manifest cannot be parsed") from exc
    if (
        manifest.get("schema") != "arvectum_original_eis_source_documents_v1"
        or manifest.get("source_observation_id") != src.observation_id
        or manifest.get("archived_original_zip_sha256") != src.original_sha256
        or manifest.get("selected_notice_xml_sha256") != classified["notice_xml_sha256"]
        or manifest.get("selected_notice_source_version") != classified["source_version"]
        or manifest.get("title_original") != _title_from_original(xml)
        or manifest.get("all_original_binaries_saved") is not True
        or manifest.get("source_current_live_status_verified") is not False
        or not 1 <= len(refs) <= MAX_FILES
        or len(manifest.get("attachments", [])) != len(refs)
    ):
        raise SourcePreparationError("original manifest not source/version consistent")
    repo = TenderRepository(session)
    tender = repo.get_tender_by_registry_number(number)
    if (
        tender is None or tender.law_type != "44fz"
        or not isinstance(tender.raw_payload, dict)
        or tender.raw_payload.get("owner_attested_original_archive_sha256") != src.original_sha256
        or tender.raw_payload.get("archived_notice_xml_sha256") != classified["notice_xml_sha256"]
        or tender.raw_payload.get("source_observation_id") != src.observation_id
    ):
        raise SourcePreparationError("Tender Research tender not bound to same source ZIP/XML")
    original_version = f"eis-archived-v{classified['source_version']}"
    criteria_id = original_version + "-derived-criteria-percent"
    documents = [
        doc for doc in tender.documents
        if doc.source_document_id != criteria_id
        and not str(doc.source_document_id or "").endswith("-derived-full-xml")
    ]
    derived = [
        doc for doc in tender.documents
        if str(doc.source_document_id or "").endswith("-derived-full-xml")
    ]
    criteria_derived = [
        doc for doc in tender.documents if doc.source_document_id == criteria_id
    ]
    if len(documents) != len(refs) or len(derived) > 1 or len(criteria_derived) > 1:
        raise SourcePreparationError("Tender Research original document count differs from original")
    if criteria_derived:
        from scripts.procurement_llm.official_eis_criteria_percent import context_blob
        from scripts.procurement_llm.source_derived_docx import same_docx_content

        expected_binary, receipt = context_blob(src, root=root)
        document = criteria_derived[0]
        check = Path(document.local_path) if document.local_path else None
        if (
            check is None or check.is_symlink() or not check.is_file()
            or not check.resolve().is_relative_to(root.resolve())
            or stat.S_IMODE(check.stat().st_mode) != 0o600
            or not same_docx_content(check.read_bytes(), expected_binary)
            or document.sha256 != _digest(check.read_bytes())
            or not isinstance(document.raw_meta, dict)
            or document.raw_meta.get("source_original_archive_sha256") != src.original_sha256
            or document.raw_meta.get("criteria_original_sha256") != receipt["criteria_original_sha256"]
        ):
            raise SourcePreparationError("derived criteria percent document stale or tampered")
    if derived:
        from scripts.procurement_llm.official_eis_xml_context import source_context_blob
        from scripts.procurement_llm.source_derived_docx import same_docx_content

        expected_bytes, _derived_receipt = source_context_blob(src, root=root)
        doc = derived[0]
        check = Path(doc.local_path) if doc.local_path else None
        if (
            check is None or check.is_symlink() or not check.is_file()
            or not check.resolve().is_relative_to(root.resolve())
            or stat.S_IMODE(check.stat().st_mode) != 0o600
            or not same_docx_content(check.read_bytes(), expected_bytes)
            or doc.sha256 != _digest(check.read_bytes())
            or doc.raw_meta.get("source_original_zip_sha256") != src.original_sha256
            or doc.raw_meta.get("source_notice_xml_sha256") != classified["notice_xml_sha256"]
        ):
            raise SourcePreparationError("derived official XML document stale or tampered")
    indexed_roles = 0
    for idx, (ref, entry) in enumerate(zip(refs, manifest["attachments"], strict=True), 1):
        expected_name = _safe_name(ref["name"])
        sha = entry.get("original_binary_sha256")
        expected_url_hash = _digest(ref["url"].encode("utf-8"))
        if (
            entry.get("source_index") != idx
            or entry.get("original_name") != expected_name
            or entry.get("source_url_sha256") != expected_url_hash
            or entry.get("source_role_hint") != (ref.get("document_kind") or "attachment")
            or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha)
        ):
            raise SourcePreparationError("attachment not identical to original XML reference")
        filename = f"{idx:02d}-{sha}{Path(expected_name).suffix.lower()}"
        original = path.parent / filename
        if (
            entry.get("owner_private_original_path") != str(original)
            or original.is_symlink() or not original.is_file()
            or stat.S_IMODE(original.stat().st_mode) != 0o600
            or _digest(original.read_bytes()) != sha
        ):
            raise SourcePreparationError("original attachment byte checksum conflict")
        matches = [
            doc for doc in documents
            if doc.source_document_id == (
                f"eis-archived-v{classified['source_version']}-{idx:02d}"
            ) and doc.sha256 == sha and doc.local_path == str(original)
        ]
        if len(matches) != 1:
            raise SourcePreparationError("Tender Research document not equal to original")
        if entry["binary_type"] == "DOCX_MAIN_BODY_OK":
            indexed_roles += 1
    return {
        "number": number,
        "tender_id": tender.id,
        "original_archive_sha256": src.original_sha256,
        "source_notice_xml_sha256": classified["notice_xml_sha256"],
        "registered_documents_verified": len(refs),
        "source_indexable_docx_count": indexed_roles,
        "has_verified_current_legal_status": False,
    }


def index_existing_source_set(
    session: Session, number: str, *, root: Path = OWNER_PRIVATE,
) -> dict:
    """Explicit owner-only apply, following a full validated prewrite backup."""
    evidence = verify_registered_exact_source_set(session, number, root=root)
    if evidence["source_indexable_docx_count"] < 1:
        raise SourcePreparationError("no validated document available for Data Platform")
    # The original EIS ZIP/XML is already privately stored; its typed notice
    # fields and all technical object characteristics are a separately marked
    # derived DOCX in the *same* source-SHA-bound TenderResearch collection.
    from scripts.procurement_llm.official_eis_xml_context import (
        store_xml_derived_context,
    )
    sources = [
        item for item in source_rows(session)
        if item.platform == "eis" and item.procurement_ref == number
    ]
    if len(sources) != 1 or sources[0].original_sha256 != evidence["original_archive_sha256"]:
        raise SourcePreparationError("source version changed before XML-derived ingest")
    derived = store_xml_derived_context(session, sources[0], root=root)
    from scripts.procurement_llm.official_eis_criteria_percent import (
        NUMBER as SMOLENSK_CRITERIA_NUMBER,
    )
    from scripts.procurement_llm.official_eis_criteria_percent import (
        store_criteria_context,
    )

    criteria = (
        store_criteria_context(session, sources[0], root=root)
        if number == SMOLENSK_CRITERIA_NUMBER else None
    )
    session.commit()
    evidence = verify_registered_exact_source_set(session, number, root=root)
    from src.tender_research.rag.prepare_service import prepare_tender_for_analysis

    finished = prepare_tender_for_analysis(number, session=session)
    if not (
        finished.ready_for_analysis is True
        and finished.status in {"completed", "completed_with_warnings"}
        and finished.chunks_total >= 1
        and finished.embeddings_total >= finished.chunks_total
    ):
        raise SourcePreparationError("actual Data Platform indexing not ready")
    verify_registered_exact_source_set(session, number, root=root)
    return {
        **evidence,
        "index_status": finished.status,
        "xml_context_indexed": True,
        "criteria_source_percentages_verified": (
            criteria["verified_percentages"] if criteria else None
        ),
        "criteria_original_docx_sha256": (
            criteria["original_criteria_sha256"] if criteria else None
        ),
        "criteria_derived_docx_sha256": (
            criteria["derived_sha256"] if criteria else None
        ),
        "xml_original_sha256": derived["source_xml_sha256"],
        "xml_derived_docx_sha256": derived["docx_sha256"],
        "xml_technical_characteristics_included": derived["full_xml_characteristics"],
        "index_contains_exact_archival_nmc": derived["notice_nmck_rub"],
        "indexed_chunks": finished.chunks_total,
        "indexed_embeddings": finished.embeddings_total,
        "source_llm_ready_for_independent_check": True,
        "generated_answer": False,
        "training_gold_promoted": False,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--number", default="0163200000326005243")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--index-only", action="store_true",
                        help="Use previously saved official docs, never download them again")
    parser.add_argument("--confirm-database", choices=["arvectum"])
    args = parser.parse_args()
    if args.apply and args.confirm_database != "arvectum":
        parser.error("explicit canonical DB approval required")
    with single_runner():
        # Full prewrite snapshot before source files, registration or Data
        # Platform indexing; no new PostgreSQL schema or credentials.
        backup = fresh_pg_backup() if args.apply else None
        if args.index_only:
            engine = create_engine(_engine_url())
            try:
                with Session(engine) as session:
                    result = (
                        index_existing_source_set(session, args.number)
                        if args.apply else
                        verify_registered_exact_source_set(session, args.number)
                    )
                    if not args.apply:
                        session.rollback()
            finally:
                engine.dispose()
        else:
            result = prepare(args.number, apply=args.apply)
        if backup is not None:
            result["prewrite_full_pg_backup_sha256"] = backup["sha256"]
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
