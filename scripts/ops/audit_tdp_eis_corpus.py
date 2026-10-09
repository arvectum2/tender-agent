"""Read-only structural baseline of genuine EIS run folders for R5 acceptance.

This is NOT factual/manual quality sign-off. Does not download documents,
reanalyze runs, contact EIS, expose file bodies or change any run metadata.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

_NUMBER = re.compile(r"(?:\d{11}|\d{19})\Z")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.is_symlink():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError):
        return None
    return obj if isinstance(obj, dict) else None


def _original_exists(folder: Path, stored_name: Any) -> bool:
    if not isinstance(stored_name, str) or not stored_name:
        return False
    directory = (folder / "input").resolve()
    path = (directory / stored_name).resolve()
    return path.is_relative_to(directory) and path.is_file() and not path.is_symlink()


def _one_run(folder: Path) -> dict[str, Any] | None:
    metadata = _read_json(folder / "metadata.json")
    if metadata is None:
        return None
    number = str(metadata.get("procurement_id") or "").strip()
    if not _NUMBER.fullmatch(number):
        return None
    files = metadata.get("files") or []
    if not isinstance(files, list):
        files = []
    files = [file for file in files if isinstance(file, dict)]
    present = sum(_original_exists(folder, file.get("stored_name")) for file in files)
    extracted = sum(bool(file.get("extracted_text_available")) for file in files)
    outputs = folder / "output"
    report = _read_json(outputs / "report.json")
    verified = metadata.get("_verified_notice_facts")
    provenance = metadata.get("ai_runtime_provenance")
    model_invoked = bool(provenance.get("llm_invoked")) if isinstance(provenance, dict) else False

    # Restrict surfaced fields to identifiers, booleans and counts; no customer
    # contacts, contract excerpts, raw user paths or private purchase details.
    return {
        "procurement_number": number,
        "run_id": folder.name,
        "status": str(metadata.get("status") or "unknown"),
        "file_count": len(files),
        "original_files_present": present,
        "files_marked_extracted": extracted,
        "report_available": report is not None,
        "eis_xml_evidence_record": isinstance(verified, dict) and bool(verified),
        "model_invoked_recorded": model_invoked,
        "analysis_mode": str(metadata.get("analysis_mode") or "unknown"),
        "has_unavailable_originals": present < len(files),
    }


def audit_corpus(root: Path) -> dict[str, Any]:
    by_number: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for folder in sorted(root.iterdir()) if root.is_dir() else []:
        if not folder.is_dir() or folder.is_symlink():
            continue
        entry = _one_run(folder)
        if entry is not None:
            by_number[entry["procurement_number"]].append(entry)
    chosen = []
    for number, runs in sorted(by_number.items()):
        best = max(
            runs,
            key=lambda row: (
                row["original_files_present"],
                row["files_marked_extracted"],
                int(row["report_available"]),
                int(row["eis_xml_evidence_record"]),
                row["run_id"],
            ),
        )
        chosen.append(best)
    complete = sum(
        row["file_count"] > 0
        and row["file_count"] == row["original_files_present"]
        and row["files_marked_extracted"] == row["file_count"]
        and row["report_available"]
        for row in chosen
    )
    return {
        "contract": "tdp-r5-eis-run-structural-baseline-v1",
        "read_only": True,
        "acceptance_quality_verified": False,
        "unique_procurements": len(chosen),
        "all_eis_runs": sum(map(len, by_number.values())),
        "best_run_structurally_complete": complete,
        "best_run_originals_missing": sum(x["has_unavailable_originals"] for x in chosen),
        "best_run_with_report": sum(x["report_available"] for x in chosen),
        "best_run_with_eis_xml_fact_record": sum(x["eis_xml_evidence_record"] for x in chosen),
        "best_run_with_recorded_llm_invocation": sum(x["model_invoked_recorded"] for x in chosen),
        "procurements": chosen,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = audit_corpus(args.root)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out and str(args.out) == "-":
        print(encoded, end="")
    else:
        if args.out:
            args.out.write_text(encoded, encoding="utf-8")
        print(json.dumps(
            {key: value for key, value in report.items() if key != "procurements"},
            ensure_ascii=False,
        ))


if __name__ == "__main__":
    main()
