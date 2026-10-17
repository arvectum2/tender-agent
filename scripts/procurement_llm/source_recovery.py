"""Read-only recovery of historical Tender Agent reports and official EIS receipt metadata.

Never creates/rewrites reports, never infers tender participation or legal gold.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy import create_engine, func, select

from scripts.procurement_llm.import_candidates import _engine_url
from src.tender_research.models import TenderAnalysisRun

_NOTICE = re.compile(r"^[0-9]{19}$")
_SKIP = {".git", ".venv", "node_modules", "__pycache__", ".next", ".pytest_cache"}
_MAX_XML = 20 * 1024 * 1024
_MAX_CANDIDATE_REPORT = 20 * 1024 * 1024


def _tag(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def inspect_final_eis_protocol(
    archive_path: Path, procurement_ref: str, app_number: str
) -> dict:
    """Verify a specific application using original ZIP bytes only; no identity claim.

    Parse EIS final protocol without extracting to disk or copying its contents.
    """
    if not _NOTICE.fullmatch(procurement_ref):
        raise ValueError("Expected a 19-digit official procurement reference")
    if not app_number.isdigit() or len(app_number) > 9:
        raise ValueError("Expected numeric application number")
    if not archive_path.is_file() or archive_path.is_symlink():
        raise ValueError("Missing or symlinked original archive")

    digest = sha256()
    with archive_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    with ZipFile(archive_path) as archive:
        members = [
            m for m in archive.infolist()
            if Path(m.filename).name.lower().startswith(
                "epprotocolezk2020final_" + procurement_ref
            ) and m.filename.lower().endswith(".xml")
        ]
        if len(members) != 1:
            raise ValueError("Exactly one matching EIS final protocol is required")
        member = members[0]
        if member.file_size > _MAX_XML:
            raise ValueError("Unreasonably large EIS protocol")
        original = archive.read(member)
    if b"<!DOCTYPE" in original.upper() or b"<!ENTITY" in original.upper():
        raise ValueError("XML entities/DTD are prohibited")
    root = ET.fromstring(original)
    matches = []
    for element in root.iter():
        if _tag(element.tag) != "applicationInfo":
            continue
        leaves = {
            _tag(child.tag): (child.text or "").strip()
            for child in element.iter() if len(child) == 0
        }
        if leaves.get("appNumber") == app_number:
            matches.append(leaves)
    if len(matches) != 1:
        raise ValueError("Application number absent or ambiguous in final protocol")
    match = matches[0]
    return {
        "procurement_ref": procurement_ref,
        "application_number": app_number,
        "admitted_in_protocol": match.get("admitted"),
        "final_price_rub": match.get("finalPrice"),
        "application_rating": match.get("appRating"),
        "original_archive_sha256": digest.hexdigest(),
        "protocol_xml_sha256": sha256(original).hexdigest(),
        "protocol_member": member.filename,
        "applicant_identity_verified": False,
        "scope": "archival_official_protocol_application_fields_only",
        "mutations": 0,
    }


def report_missing_rows(data_root: Path) -> list[dict]:
    """Read all DB report refs using a genuinely read-only PG transaction."""
    engine = create_engine(_engine_url())
    try:
        if engine.dialect.name != "postgresql":
            raise ValueError("Must connect to existing PostgreSQL arvectum")
        missing = []
        with engine.connect() as conn, conn.begin():
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            rows = conn.execute(select(
                TenderAnalysisRun.id,
                TenderAnalysisRun.registry_number,
                TenderAnalysisRun.report_path,
                func.length(TenderAnalysisRun.report_markdown_preview),
            )).all()
        for run_id, ref, report_path, preview_length in rows:
            if not report_path:
                continue
            original = Path(report_path)
            if original.is_absolute():
                candidate = original
            elif original.parts[:3] == ("data", "rag", "reports") and ".." not in original.parts:
                candidate = data_root / original
            else:
                continue
            if candidate.is_file() and not candidate.is_symlink():
                continue
            missing.append({
                "run_id": str(run_id),
                "procurement_ref": ref,
                "basename": original.name,
                "has_saved_preview": bool(preview_length),
            })
        return missing
    finally:
        engine.dispose()


def locate_original_report_names(
    missing: list[dict], roots: list[Path], *, max_files: int = 300000
) -> dict:
    """Find filename candidates without moving any bytes. Never call them verified."""
    names = {row["basename"] for row in missing}
    hit_names = set()
    candidate_paths = 0
    searched = 0
    skipped_roots = 0
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            skipped_roots += 1
            continue
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [
                n for n in dirs if n not in _SKIP
                and not (Path(directory) / n).is_symlink()
            ]
            for filename in files:
                searched += 1
                if searched > max_files:
                    raise RuntimeError("File search budget exceeded: explicitly narrow roots")
                if filename not in names:
                    continue
                path = Path(directory) / filename
                if path.is_symlink() or not path.is_file():
                    continue
                if path.stat().st_size > _MAX_CANDIDATE_REPORT:
                    continue
                hit_names.add(filename)
                candidate_paths += 1
    return {
        "missing_report_rows": len(missing),
        "missing_report_unique_basenames": len(names),
        "by_registry": dict(sorted(Counter(row["procurement_ref"] for row in missing).items())),
        "candidate_report_basenames_found": len(hit_names),
        "candidate_report_paths_found_unverified": candidate_paths,
        "searched_file_entries": searched,
        "unavailable_roots": skipped_roots,
        "restored": 0,
        "mutations": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol-zip", type=Path)
    parser.add_argument("--procurement-ref")
    parser.add_argument("--app-number")
    parser.add_argument("--data-root", type=Path, default=Path("/Volumes/ArvectumSSD/Arvectum"))
    parser.add_argument("--report-search-root", action="append", type=Path, default=[])
    parser.add_argument("--max-files", type=int, default=300000)
    args = parser.parse_args(argv)
    if args.protocol_zip:
        if not args.procurement_ref or not args.app_number:
            parser.error("--protocol-zip requires --procurement-ref and --app-number")
        result = inspect_final_eis_protocol(args.protocol_zip, args.procurement_ref, args.app_number)
    else:
        missing = report_missing_rows(args.data_root)
        roots = args.report_search_root or [args.data_root / "data", args.data_root / "archive"]
        result = locate_original_report_names(missing, roots, max_files=args.max_files)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
