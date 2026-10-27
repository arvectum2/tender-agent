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

SUPPORTED = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".xml"}


def ingest(*, sources: Path, output: Path, dp_source: Path,
           max_files: int = 30, max_bytes: int = 20 * 1024 * 1024) -> dict:
    if not 1 <= max_files <= 500 or sources.is_symlink() or not sources.is_dir():
        raise ValueError("Invalid source scope")
    if not (dp_source / "arvectum_data" / "documents" / "ingest.py").is_file():
        raise ValueError("Data Platform source tree not found")
    sys.path.insert(0, str(dp_source))
    from arvectum_data.documents.ingest import ingest_file
    records = []
    files = sorted(p for p in sources.rglob("*") if p.is_file() and not p.is_symlink()
                   and p.suffix.lower() in SUPPORTED)
    for path in files[:max_files]:
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
            records.append({"path": str(path), "sha256": sha,
                            "document_id": result.document.document_id,
                            "extraction_status": "extracted" if extracted_text.strip() else result.document.extraction_status,
                            "extraction_method": fallback["method"] if fallback else "data_platform",
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
        "errors": sum(r.get("status") == "extraction_error" for r in records)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sources", type=Path, required=True)
    p.add_argument("--dp-source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-files", type=int, default=30)
    a = p.parse_args()
    print(json.dumps(ingest(sources=a.sources, dp_source=a.dp_source,
                            output=a.output, max_files=a.max_files),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
