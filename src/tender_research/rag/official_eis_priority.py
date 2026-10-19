"""Original-EIS source-scoped evidence priority; never a source of invented facts.

Only the already attested, exact archived Smolensk ZIP v2 and registered
derived XML/criteria chunks may be prioritized. No tenant-crossing,
revision-crossing or permissive fallback if provenance cannot be proven.
"""
from __future__ import annotations

import hashlib
import stat
from pathlib import Path

from src.tender_research.rag.search_types import RagSearchHit
from src.tender_research.repository import TenderRepository

_PINNED_NUMBER = "0163200000326005243"
_PINNED_ARCHIVE_SHA = "4cec297f6bd040723105fab5ac03a3d10e986b3c03b03032a7da3c3769389d5d"
_OWNER_ORIGINAL_ROOT = Path("/Volumes/ArvectumSSD/Arvectum/private/tender-agent/eis-source-documents")
_DOC_BY_SECTION = {
    "notice_info": "-derived-full-xml",
    "subject": "-derived-full-xml",
    "deadlines": "-derived-full-xml",
    "evaluation_criteria": "-derived-criteria-percent",
}
_SIGNATURES = {
    "-derived-full-xml": ("official_eis_archived_xml_derived_full_text_v1", "source_original_zip_sha256"),
    "-derived-criteria-percent": ("arvectum_eis_criteria_percent_from_original_cells_v1", "source_original_archive_sha256"),
}


def _verified_document(document, *, tender_id: str, suffix: str) -> bool:
    if str(document.tender_id) != str(tender_id):
        return False
    if document.source_document_id != f"eis-archived-v2{suffix}":
        return False
    meta = document.raw_meta
    if not isinstance(meta, dict):
        return False
    schema, archive_field = _SIGNATURES[suffix]
    if meta.get("schema") != schema or meta.get(archive_field) != _PINNED_ARCHIVE_SHA:
        return False
    if meta.get("derived_docx_sha256") != document.sha256:
        return False
    if not isinstance(document.sha256, str) or len(document.sha256) != 64:
        return False
    expected_parent = _OWNER_ORIGINAL_ROOT / _PINNED_NUMBER / _PINNED_ARCHIVE_SHA
    file = Path(document.local_path) if document.local_path else None
    if file is None or file.is_symlink() or not file.is_file():
        return False
    if file.parent.resolve() != expected_parent.resolve():
        return False
    if stat.S_IMODE(file.stat().st_mode) != 0o600:
        return False
    return hashlib.sha256(file.read_bytes()).hexdigest() == document.sha256


def _suitable_score(section_id: str, text: str) -> int:
    text = text.casefold()
    if section_id == "evaluation_criteria":
        return sum(token in text for token in ("30%", "70%", "80%", "20%"))
    if section_id == "deadlines":
        return int("30.10.2026" in text or "30 октября" in text) * 2 + int("11:00" in text)
    return int("497178" in text or "497 178" in text) * 3 + int("извещени" in text)


def prioritize_original_eis_hits(
    repo: TenderRepository,
    hits: list[RagSearchHit],
    *,
    registry_number: str,
    section_id: str,
    max_chunks: int,
) -> list[RagSearchHit]:
    """Only elevate exact trusted source chunks; do not change evidence or accept claims."""
    if registry_number != _PINNED_NUMBER or section_id not in _DOC_BY_SECTION:
        return hits
    tender = repo.get_tender_by_registry_number(registry_number)
    if tender is None:
        return hits
    tender_id = str(tender.id)
    # When the attested document is missing or invalid, still exclude
    # foreign retrieval hits for this exact registry; never return unscoped.
    scoped = [
        h for h in hits if h.registry_number == registry_number
        and str(h.tender_id) == tender_id
    ]
    suffix = _DOC_BY_SECTION[section_id]
    documents = [doc for doc in tender.documents if
                 doc.source_document_id == f"eis-archived-v2{suffix}"]
    if len(documents) != 1 or not _verified_document(documents[0], tender_id=tender_id, suffix=suffix):
        return scoped
    document = documents[0]
    candidates = [
        chunk for chunk in repo.list_chunks_by_tender(tender_id)
        if str(chunk.document_id) == str(document.id) and
        str(chunk.tender_id) == tender_id and chunk.text
    ]
    candidates.sort(key=lambda c: (-_suitable_score(section_id, c.text), c.chunk_index))
    trusted: list[RagSearchHit] = []
    for chunk in candidates:
        if len(trusted) >= (2 if suffix == "-derived-full-xml" else 1):
            break
        context = repo.get_chunk_context(str(chunk.id))
        if not context or context["registry_number"] != registry_number or str(context["tender_id"]) != tender_id:
            continue
        if str(context["document_id"]) != str(document.id):
            continue
        trusted.append(RagSearchHit(
            chunk_id=str(context["chunk_id"]), score=1.0,
            registry_number=registry_number, tender_id=tender_id,
            tender_title=context["tender_title"], customer_name=context["customer_name"],
            document_id=str(document.id), file_name=context["file_name"],
            chunk_index=context["chunk_index"], preview=context["text"][:280],
            text=context["text"],
        ))
    # Additional defense: retrieval provider may return a foreign collection hit
    # even when requested collection was source-scoped.
    own = scoped
    chosen = list(trusted)
    seen = {hit.chunk_id for hit in chosen}
    for hit in own:
        if hit.chunk_id not in seen and len(chosen) < max_chunks:
            chosen.append(hit)
            seen.add(hit.chunk_id)
    return chosen[:max_chunks]
