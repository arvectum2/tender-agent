"""Append-only source-backed report corrections; original model artifacts stay immutable.

The revision manifest is private per-run storage, never a global search index.
Reject corrupted correction records instead of exposing superseded report text.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException

REVISION_MANIFEST = "report-revision.json"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_revision(output: Path, run_id: str) -> dict[str, Any] | None:
    manifest = output / REVISION_MANIFEST
    if not manifest.exists():
        return None
    try:
        record = json.loads(manifest.read_text(encoding="utf-8"))
        if record.get("run_id") != run_id or record.get("revision") != "source-correction-v1":
            raise ValueError("unexpected revision identity")
        if record.get("registry_number") != "0349100009326000005":
            raise ValueError("report revision for wrong procurement")
        for filename, expected in (
            ("report.json", record.get("original_report_json_sha256")),
            ("report.html", record.get("original_report_html_sha256")),
            ("../metadata.json", record.get("original_metadata_sha256")),
        ):
            if not isinstance(expected, str) or not _SHA.fullmatch(expected):
                raise ValueError("unbound original report metadata")
            if _digest(output / filename) != expected:
                raise ValueError("historical original report changed")
        files = record.get("original_source_files")
        if not isinstance(files, list) or len(files) != 9:
            raise ValueError("original nine-file source inventory changed")
        for item in files:
            name, expected = item.get("stored_name"), item.get("sha256")
            if not isinstance(name, str) or not name:
                raise ValueError("unsafe original file")
            rel = Path(name)
            if (rel.is_absolute() or ".." in rel.parts
                    or not (len(rel.parts) == 1 or
                            (len(rel.parts) == 2 and rel.parts[0] == "extracted"))):
                raise ValueError("unsafe original file")
            if not isinstance(expected, str) or not _SHA.fullmatch(expected):
                raise ValueError("unbound original file SHA")
            original = output.parent / "input" / rel
            if (not original.resolve().is_relative_to((output.parent / "input").resolve())
                    or original.is_symlink() or not original.is_file()
                    or _digest(original) != expected):
                raise ValueError("original source changed")
        revision_dir = output / "report-revisions" / "source-correction-v1"
        if revision_dir.is_symlink() or not revision_dir.is_dir():
            raise ValueError("unsafe revision directory")
        for kind in ("json", "html"):
            filename = revision_dir / f"report.{kind}"
            expected = record.get(f"revision_report_{kind}_sha256")
            if (filename.is_symlink() or not filename.is_file()
                    or not isinstance(expected, str) or not _SHA.fullmatch(expected)
                    or _digest(filename) != expected):
                raise ValueError("corrected report missing or changed")
        return record
    except (OSError, ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=409, detail="Source-corrected report integrity requires review") from exc


def published_report_path(output: Path, run_id: str, kind: str) -> Path:
    if kind not in {"json", "html"}:
        raise ValueError("report type unsupported")
    revision = verified_revision(output, run_id)
    if revision is not None:
        return output / "report-revisions" / "source-correction-v1" / f"report.{kind}"
    return output / f"report.{kind}"
