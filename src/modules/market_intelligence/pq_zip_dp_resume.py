"""Checkpointed, bounded Data Platform ingestion for verified ZIP member corpus."""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .pq_dp_ingest import ingest


def run(*, source_root: Path, runtime: Path, dp_source: Path,
        max_files: int = 24, extractor=ingest) -> dict:
    if not 1 <= max_files <= 100 or source_root.is_symlink() or not source_root.is_dir():
        raise ValueError("Invalid bounded ZIP ingestion")
    manifest = source_root / "source-manifest.json"
    raw = manifest.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    source = json.loads(raw)
    if source.get("schema_version") != "pq-verified-zip-members/1":
        raise ValueError("Invalid ZIP member source provenance")
    total = len(source["files"])
    cursor_file = runtime / "zip-dp-cursor.json"
    previous = json.loads(cursor_file.read_text(encoding="utf-8")) if cursor_file.exists() else {}
    offset = int(previous.get("next_offset", 0)) if previous.get("source_manifest_sha256") == sha else 0
    if offset >= total:
        return {"status": "complete", "source_count": total, "next_offset": offset,
                "files_inspected": 0}
    output = runtime / f"dp-zip-batch-{offset:04d}.json"
    result = extractor(sources=source_root, output=output, dp_source=dp_source,
                       max_files=max_files, start_offset=offset, ocr_empty=True)
    if result.get("errors"):
        return {"status": "needs_attention", "next_offset": offset,
                "source_count": total, **result}
    next_offset = offset + result["files_inspected"]
    checkpoint = {"schema_version": "pq-zip-dp-cursor/1",
                  "source_manifest_sha256": sha,
                  "next_offset": next_offset, "source_count": total,
                  "last_batch": str(output)}
    runtime.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=runtime,
                                     prefix=".cursor-", delete=False) as f:
        temp = Path(f.name)
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, cursor_file)
    return {"status": "complete" if next_offset >= total else "in_progress",
            "next_offset": next_offset, "source_count": total, **result}
