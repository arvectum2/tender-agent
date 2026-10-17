"""Independent text-readiness overlay for all 96 source-attested archive attachments.

Read-only replay of immutable private source/extraction receipts. Nonempty
extracted text means evidence is searchable, NOT complete semantic/legal review,
not all spreadsheet cells, formulas, scans, tables or signed human gold.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_PRIOR50_SHA = "f352421119f525743d8b16adb7b1980e359087af5006bd92ae6409088f2df10a"
_FRESH25_SHA = "e2f86213e48a1fdf7fa146be22de77e3add59ed6d94b62713975963a2a5adfe8"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_original_text_receipt(path: Path, expected_sha: str, expected_count: int) -> list[dict]:
    raw = path.read_bytes()
    if len(raw) > 300_000 or _sha(raw) != expected_sha:
        raise ValueError("original document extracted-text receipt is not pinned")
    entries = json.loads(raw)
    if not isinstance(entries, list) or len(entries) != expected_count:
        raise ValueError("historical original text receipt case count differs")
    return entries


def _verify_text_location(root: Path, registry: str, filename: str, digest: str, chars: int) -> None:
    if (not re.fullmatch(r"\d{19}", registry) or not isinstance(filename, str)
            or Path(filename).name != filename or not filename.endswith(".txt")
            or not re.fullmatch("[a-f0-9]{64}", digest)
            or not isinstance(chars, int) or chars < 60):
        raise ValueError("original normalized text locator is not trustworthy")
    path = root / registry / filename
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("original normalized source file not found in allowed evidence directory")
    raw = path.read_bytes()
    if _sha(raw) != digest or len(raw.decode("utf8")) != chars:
        raise ValueError("original document normalized text was modified or incomplete")
    if not raw.decode("utf8").strip():
        raise ValueError("only blank text was extracted from original")


def verify_all_96_original_texts(
    *,
    root: Path,
    attachment_inventory: dict,
    additional_document_audit: dict,
) -> dict:
    archive = {
        (case["registry_number"], doc["original_document_sha256"]): doc
        for case in attachment_inventory["cases"]
        for doc in case["documents"]
    }
    expected_methods = {
        "OLDER_VERIFIED_TLS_RECHECK": 50,
        "ADDITIONAL_ORIGINAL_DOWNLOAD": 21,
        "NEWLY_RETRIEVED_OFFICIAL_SOURCE": 25,
    }
    if (attachment_inventory.get("case_count") != 20
            or attachment_inventory.get("source_shas_attested") != 96
            or attachment_inventory.get("evidence_methods") != expected_methods
            or len(archive) != 96):
        raise ValueError("not all chosen EIS original attachments have unique SHA provenance")
    evidence = root / "ai-expert-20261012"
    previous_dir = evidence / "competitive-prior50-original-text-20261014"
    previous = _read_original_text_receipt(
        previous_dir / "source-text50-private-receipt.json", _PRIOR50_SHA, 50
    )
    recent_dir = evidence / "competitive-25-original-text-20261014"
    recent = _read_original_text_receipt(
        recent_dir / "text-extraction-private-receipt.json", _FRESH25_SHA, 25
    )
    covered = set()
    characters = 0
    for group, folder, method in (
        (previous, previous_dir, "OLDER_VERIFIED_TLS_RECHECK"),
        (recent, recent_dir, "NEWLY_RETRIEVED_OFFICIAL_SOURCE"),
    ):
        for record in group:
            if method == "OLDER_VERIFIED_TLS_RECHECK":
                number = record["registry_number"]
                origin = record["original_sha256"]
                filename = record["private_text_filename"]
                digest = record["normalized_sha256"]
                chars = record["normalized_chars"]
                status = record["text_state"]
                source_name = record["original_name"]
            else:
                number = record["registry_number"]
                origin = record["origin_sha256"]
                filename = record["text_private_file"]
                digest = record["text_sha256"]
                chars = record["text_chars"]
                status = record["text_status"]
                source_name = record["source_name"]
            if status != "TEXT_EXTRACTED":
                raise ValueError("document exists but readable text was not attested")
            doc = archive.get((number, origin))
            if not doc or doc["source_proof"] != method or doc["original_filename"] != source_name:
                raise ValueError("normalized text belongs to another selected original EIS revision")
            _verify_text_location(folder, number, filename, digest, chars)
            if (number, origin) in covered:
                raise ValueError("duplicate original document text match")
            covered.add((number, origin))
            characters += chars
    extra = {
        k for k, entry in archive.items()
        if entry["source_proof"] == "ADDITIONAL_ORIGINAL_DOWNLOAD"
    }
    if not (
        len(covered) == 75 and len(extra) == 21
        and covered.isdisjoint(extra)
        and additional_document_audit["original_binaries_sha_verified"] == 21
        and additional_document_audit["normalized_texts_sha_verified"] == 22
    ):
        raise ValueError("original recovered source and saved text evidence incomplete")
    return {
        "archived_original_attachments": 96,
        "attachments_with_nonempty_source_text": 96,
        "older_original_documents_text": 50,
        "new_original_documents_text": 21,
        "fresh_20261014_original_documents_text": 25,
        "additional_inner_original_text_units": 22,
        "older_and_fresh_text_characters": characters,
        "text_extraction_completeness_asserted": False,
        "full_legal_semantic_reviews_signed": 0,
        "current_EIS_revision_verified": False,
        "bid_ready": False,
        "note": (
            "All 96 original archived attachments have nonempty recorded text. "
            "This does not attest every table cell, spreadsheet formula, PDF scan "
            "or the legal completeness of extracted source."
        ),
    }
