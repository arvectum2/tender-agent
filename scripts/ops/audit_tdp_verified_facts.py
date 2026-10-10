"""Read-only R5 audit: do authoritative notice facts survive report materialization?

This checks persisted SOURCE RECORD to CANONICAL RECORD presence and locator,
not whether the extraction itself is accurate or the original legal document
is authentic. Never logs values, source passages, customer data or passwords.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

FACT_KEYS = ("procurement_title", "application_deadline", "nmck")
VALID_NUMBER = re.compile(r"(?:\d{11}|\d{19})\Z")
UNKNOWN = frozenset({"", "unknown", "none", "null", "н/д", "неизвестно"})


def _dict_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.is_symlink():
        return None
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    return result if isinstance(result, dict) else None


def _known(value: Any) -> bool:
    return isinstance(value, (str, int, float)) and str(value).strip().casefold() not in UNKNOWN


def compare_saved_notice_fact_projections(
    metadata: dict[str, Any], canonical: dict[str, Any] | None
) -> dict[str, str]:
    """Classify preservation, without publishing any actual fact value."""
    registry = str(metadata.get("procurement_id") or "").strip()
    source = metadata.get("_verified_notice_facts")
    if not VALID_NUMBER.fullmatch(registry) or not isinstance(source, dict):
        return {key: "no_verified_notice_source" for key in FACT_KEYS}
    if source.get("registry_number") != registry or not source.get("file_id"):
        return {key: "source_registry_or_file_mismatch" for key in FACT_KEYS}
    values = source.get("values")
    if not isinstance(values, dict):
        return {key: "no_verified_notice_source" for key in FACT_KEYS}
    if canonical is None:
        return {
            key: ("known_source_missing_canonical_report" if _known(values.get(key)) else "unknown_in_source")
            for key in FACT_KEYS
        }
    source_copy = canonical.get("_verified_notice_facts")
    copied = (
        isinstance(source_copy, dict)
        and source_copy.get("registry_number") == registry
        and source_copy.get("file_id") == source.get("file_id")
    )
    fields = canonical.get("field_evidence") or {}
    fields = fields if isinstance(fields, dict) else {}
    result = {}
    for key in FACT_KEYS:
        if not _known(values.get(key)):
            result[key] = "unknown_in_source"
        elif not copied:
            result[key] = "source_record_not_preserved"
        elif not _known(canonical.get(key)):
            result[key] = "known_source_became_unknown"
        elif isinstance(fields.get(key), str) and fields[key].startswith("eis-xml:"):
            result[key] = "known_source_with_original_xml_locator"
        elif isinstance(fields.get(key), str) and fields[key].startswith("eis_notice:"):
            # Official notice field reference is not necessarily a citation to
            # the original XML file. Keep that distinction visible in metrics.
            result[key] = "known_source_with_notice_field_reference_only"
        else:
            result[key] = "known_fact_missing_source_reference"
    return result


def audit_verified_facts(root: Path) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    procured: set[str] = set()
    rows = []
    if not root.is_dir():
        return {"contract": "tdp-r5-verified-fact-preservation-v1", "runs_checked": 0,
                "unique_procurements": 0, "statuses": {}, "per_run": []}
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.is_symlink():
            continue
        metadata = _dict_file(folder / "metadata.json")
        if not metadata:
            continue
        number = str(metadata.get("procurement_id") or "").strip()
        if not VALID_NUMBER.fullmatch(number):
            continue
        procured.add(number)
        projection = compare_saved_notice_fact_projections(
            metadata, _dict_file(folder / "output" / "canonical_report.json")
        )
        for status in projection.values():
            counts[status] += 1
        rows.append({
            "procurement_number": number,
            "run_id": folder.name,
            "fields": projection,
        })
    return {
        "contract": "tdp-r5-verified-fact-preservation-v1",
        "read_only": True,
        "source_extraction_legal_accuracy_verified": False,
        "runs_checked": len(rows),
        "unique_procurements": len(procured),
        "statuses": dict(sorted(counts.items())),
        "per_run": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()
    report = audit_verified_facts(args.root)
    if not args.details:
        report.pop("per_run")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
