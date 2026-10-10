"""Product-owned assembly of operator upload documents and Data Platform provenance.

The generic extraction/ZIP decoders remain elsewhere. Dependencies are passed
explicitly so file-system boundaries and evidence IDs can be regression-tested.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.modules.procurement_analysis.frozen_types import AnalyzedDocument
from src.modules.tender_operator_agent_demo.quote_normalizer import SpreadsheetSource


def collect_operator_documents(
    *,
    metadata: dict[str, Any],
    input_dir: Path,
    normalized_dir: Path,
    checked_path: Callable[[Path, str], Path],
    extract_archive: Callable[[Path, str], list[AnalyzedDocument]],
    extract_with_provenance: Callable[[str, bytes], tuple[str | None, list[str], str, Any | None]],
    project_source: Callable[..., tuple[dict[str, Any], list[dict[str, Any]]]],
    detect_role: Callable[[str], str],
) -> list[AnalyzedDocument]:
    documents: list[AnalyzedDocument] = []
    normalized_dir.mkdir(parents=True, exist_ok=True)

    for item in metadata.get("files", []):
        stored_path = checked_path(input_dir, item["stored_name"])
        ext = Path(item["stored_name"]).suffix.lower()
        if ext == ".zip":
            extracted_docs = extract_archive(stored_path, item["file_id"])
            documents.extend(extracted_docs)
            if extracted_docs:
                item["warnings"] = list(dict.fromkeys(item.get("warnings", []) + ["ZIP archive inspected in safe local mode."]))
            continue

        raw = stored_path.read_bytes()
        text, warnings, extraction_status, processed = extract_with_provenance(
            item["stored_name"], raw
        )
        evidence_chunks: list[dict[str, Any]] | None = None
        if processed is not None:
            platform_source, evidence_chunks = project_source(
                processed, file_id=item["file_id"]
            )
            item["data_platform_source"] = platform_source
            item["evidence_chunks"] = evidence_chunks
        document_kind = str(item.get("document_kind") or "").lower()
        role_from_kind = {
            "contract_draft": "contract_draft",
            "technical_specification": "technical_spec",
            "eis_notice": "notice",
        }.get(document_kind)
        role = role_from_kind or item.get("role_hint") or detect_role(item.get("display_name") or item["stored_name"])
        if text:
            normalized_name = f"{item['file_id'].lower()}-{role}.txt"
            (normalized_dir / normalized_name).write_text(text, encoding="utf-8")
        item["warnings"] = list(dict.fromkeys(item.get("warnings", []) + warnings))
        item["extracted_text_available"] = bool(text)
        item["text_extraction_status"] = extraction_status
        documents.append(
            AnalyzedDocument(
                display_name=item["display_name"],
                extension=ext,
                role=role,
                text=text,
                extracted_text_available=bool(text),
                warnings=warnings,
                source="upload",
                file_id=item["file_id"],
                raw_content=raw,
                evidence_chunks=evidence_chunks,
            )
        )
    return documents


def collect_operator_role_text(documents: list[AnalyzedDocument], role: str) -> str:
    texts = [doc.text for doc in documents if doc.role == role and doc.text]
    return "\n\n".join(texts).strip()


def collect_operator_quote_paths(
    *,
    metadata: dict[str, Any],
    input_dir: Path,
    checked_path: Callable[[Path, str], Path],
    detect_role: Callable[[str], str],
) -> list[Path]:
    paths: list[Path] = []
    for item in metadata.get("files", []):
        if detect_role(item["stored_name"]) == "tkp":
            paths.append(checked_path(input_dir, item["stored_name"]))
    return paths


def collect_operator_spreadsheet_sources(documents: list[AnalyzedDocument]) -> list[SpreadsheetSource]:
    return [
        SpreadsheetSource(
            file_id=doc.file_id,
            display_name=doc.display_name,
            source_file=doc.display_name,
            extension=doc.extension,
            raw_content=doc.raw_content or b"",
            source=doc.source,
            role_hint=doc.role,
        )
        for doc in documents
        if doc.extension in {".xlsx", ".xls"} and doc.raw_content
    ]
