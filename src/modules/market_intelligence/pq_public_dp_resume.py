"""Incremental Data Platform extraction across changing public-EIS source manifests.

Tracks SHA-bound case/document identities rather than a global offset, so
newly recovered cases do not force already verified documents to be re-read.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from .pq_dp_ingest import ingest


def _atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8",
                                     prefix=".public-dp-", delete=False) as f:
        tmp = Path(f.name)
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def run(*, source_root: Path, runtime: Path, dp_source: Path,
        max_files: int = 20, extractor=ingest) -> dict:
    if (source_root.is_symlink() or not source_root.is_dir()
            or not 1 <= max_files <= 100):
        raise ValueError("Invalid source or ingestion budget")
    manifest = json.loads((source_root / "canonical-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "pq-public-canonical/1":
        raise ValueError("Unrecognized canonical source provenance")
    records = {}
    for item in manifest["records"]:
        number = str(item.get("registry_number") or "")
        digest = item.get("member_sha256")
        filename = item.get("canonical_stored_name")
        if (not re.fullmatch(r"[0-9]{11}", number)
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or not isinstance(filename, str)
                or Path(filename).name != filename
                or not filename.startswith(digest + ".")):
            raise ValueError("Unsafe canonical manifest entry")
        records[f"{number}/{filename}"] = digest
    state_path = runtime / "public223-dp-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {
        "schema_version": "pq-public223-dp-state/1", "processed": {}, "batches": []}
    if state.get("schema_version") != "pq-public223-dp-state/1":
        raise ValueError("Unexpected Data Platform checkpoint")
    if not state["processed"]:
        # Adopt a previously completed one-shot extraction, but only when the
        # path and source SHA exactly match current canonical records.
        legacy = runtime / "dp-public223-canonical.json"
        if legacy.is_file():
            for row in json.loads(legacy.read_text(encoding="utf-8")).get("records", []):
                path = Path(row.get("path") or "")
                try:
                    name = path.relative_to(source_root).as_posix()
                except ValueError:
                    continue
                if records.get(name) == row.get("sha256") and row.get("status") != "extraction_error":
                    state["processed"][name] = row["sha256"]
    missing = [name for name in sorted(records)
               if state["processed"].get(name) != records[name]]
    if not missing:
        _atomic(state_path, state)
        return {"status": "complete", "source_count": len(records),
                "processed_count": len(records), "files_inspected": 0}
    selected = missing[:max_files]
    for name in selected:
        path = source_root / name
        if (path.is_symlink() or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != records[name]):
            raise ValueError("Canonical document changed since manifest")
    output = runtime / f"dp-public223-batch-{len(state['batches']):04d}.json"
    result = extractor(
        sources=source_root, output=output, dp_source=dp_source,
        max_files=len(selected), include_relative_paths=frozenset(selected))
    for row in json.loads(output.read_text(encoding="utf-8"))["records"]:
        name = Path(row["path"]).relative_to(source_root).as_posix()
        if name in records and records[name] == row["sha256"] and row.get("status") != "extraction_error":
            state["processed"][name] = row["sha256"]
    state["batches"].append({"file": str(output),
                             "requested": len(selected),
                             "ingested": result["files_inspected"],
                             "errors": result["errors"]})
    _atomic(state_path, state)
    still_missing = sum(state["processed"].get(name) != sha
                        for name, sha in records.items())
    return {"status": "complete" if not still_missing else "in_progress",
            "source_count": len(records),
            "processed_count": len(records) - still_missing,
            "files_inspected": result["files_inspected"],
            "extracted": result.get("extracted", 0),
            "errors": result.get("errors", 0),
            "pending": still_missing}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--dp-source", type=Path, required=True)
    p.add_argument("--max-files", type=int, default=20)
    a = p.parse_args()
    print(json.dumps(run(source_root=a.source_root, runtime=a.runtime,
                         dp_source=a.dp_source, max_files=a.max_files),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
