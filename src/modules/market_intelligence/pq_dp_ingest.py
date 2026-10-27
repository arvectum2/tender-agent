"""Read-only Data Platform extraction for locally verified PQ source documents.

Does not modify Data Platform state or equate extracted text with a signed award.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from .pq_dp_fallback import pdf_text_fallback
from .pq_scan_ocr import ocr_pdf

SUPPORTED = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".xml"}


def ingest(*, sources: Path, output: Path, dp_source: Path,
           max_files: int = 30, max_bytes: int = 20 * 1024 * 1024,
           ocr_empty: bool = False, start_offset: int = 0,
           include_relative_paths: frozenset[str] | None = None) -> dict:
    if not 1 <= max_files <= 500 or not 0 <= start_offset <= 10000 or sources.is_symlink() or not sources.is_dir():
        raise ValueError("Invalid source scope")
    if not (dp_source / "arvectum_data" / "documents" / "ingest.py").is_file():
        raise ValueError("Data Platform source tree not found")
    sys.path.insert(0, str(dp_source))
    from arvectum_data.documents.ingest import ingest_file
    records = []
    files = sorted(p for p in sources.rglob("*") if p.is_file() and not p.is_symlink()
                   and p.suffix.lower() in SUPPORTED)
    if include_relative_paths is not None:
        if any(name.startswith("/") or ".." in Path(name).parts for name in include_relative_paths):
            raise ValueError("Unsafe selected document paths")
        files = [f for f in files
                 if f.relative_to(sources).as_posix() in include_relative_paths]
    for path in files[start_offset:start_offset + max_files]:
        if path.stat().st_size > max_bytes:
            records.append({"path": str(path), "status": "oversized"})
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            result = ingest_file(path, collection_id="arvectum-pq-evidence",
                                 source_type="official_local_document",
                                 max_chars=100000)
            fallback = (pdf_text_fallback(path) if path.suffix.lower() == ".pdf"
                        and not result.document.text.strip() else None)
            extracted_text = fallback["text"] if fallback and fallback["status"] == "extracted" else result.document.text
            ocr = None
            if ocr_empty and path.suffix.lower() == ".pdf" and not extracted_text.strip():
                cache = output.parent / "ocr-cache" / (sha + ".json")
                if cache.is_file() and not cache.is_symlink():
                    ocr = json.loads(cache.read_text(encoding="utf-8"))
                    if ocr.get("source_sha256") != sha:
                        raise ValueError("OCR cache checksum mismatch")
                else:
                    ocr = ocr_pdf(path)
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    cache.write_text(json.dumps(ocr, ensure_ascii=False), encoding="utf-8")
                if ocr.get("status") == "ocr_unverified":
                    extracted_text = ocr["text"]
            records.append({"path": str(path), "sha256": sha,
                            "document_id": result.document.document_id,
                            "extraction_status": ("ocr_unverified" if ocr and ocr.get("status") == "ocr_unverified" else "extracted" if extracted_text.strip() else result.document.extraction_status),
                            "extraction_method": ocr.get("method") if ocr and ocr.get("status") == "ocr_unverified" else fallback["method"] if fallback else "data_platform",
                            "characters": len(extracted_text),
                            "chunks": len(result.chunks),
                            "text_excerpt": extracted_text[:2500]})
        except Exception as exc:
            records.append({"path": str(path), "sha256": sha,
                            "status": "extraction_error",
                            "error_type": type(exc).__name__})
    payload = {"schema_version": "pq-data-platform-extract/1",
               "source_root": str(sources), "files_inspected": len(records),
               "records": records, "signed_contracts_verified": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent,
                                     prefix=".dp-", delete=False) as f:
        temp = Path(f.name)
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, output)
    return {"files_inspected": len(records), "extracted": sum(
        r.get("extraction_status") == "extracted" for r in records),
        "errors": sum(r.get("status") == "extraction_error" for r in records),
        "ocr_unverified": sum(r.get("extraction_status") == "ocr_unverified" for r in records)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sources", type=Path, required=True)
    p.add_argument("--dp-source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-files", type=int, default=30)
    p.add_argument("--ocr-empty", action="store_true")
    p.add_argument("--start-offset", type=int, default=0)
    a = p.parse_args()
    print(json.dumps(ingest(sources=a.sources, dp_source=a.dp_source,
                            output=a.output, max_files=a.max_files, ocr_empty=a.ocr_empty, start_offset=a.start_offset),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
