"""Fail-closed saved SIBUR archive import-window audit; no network or database."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from src.modules.tender_connectors.sibur.archive_parser import CATEGORIES

HEX = re.compile(r"[0-9a-f]{64}")
INPUT = re.compile(r"([0-9a-f]{64})\.input\.json")
RESULT = re.compile(r"([0-9a-f]{64})\.result\.json")


class ImportWindowError(ValueError):
    """Do not expose original source IDs, private filenames or customer PII."""


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ImportWindowError("duplicate_json_key")
        obj[key] = value
    return obj


def _read(path: Path, limit: int) -> tuple[bytes, dict]:
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= limit):
        raise ImportWindowError("untrusted_manifest_path_or_size")
    source = path.read_bytes()
    parsed = json.loads(source, object_pairs_hook=_unique_pairs)
    if not isinstance(parsed, dict):
        raise ImportWindowError("manifest_not_object")
    return source, parsed


def audit_import_window(folder: Path, *, expected_batches: int = 166) -> dict:
    """Validate saved manifest/result pairing and approved historical cutoff."""
    if (not folder.is_absolute() or not folder.is_dir()
            or folder.is_symlink() or folder.resolve() != folder):
        raise ImportWindowError("untrusted_import_folder")
    names = [p.name for p in folder.iterdir()
             if INPUT.fullmatch(p.name) or RESULT.fullmatch(p.name)]
    inputs = {p[:64]: folder / p for p in names if INPUT.fullmatch(p)}
    results = [folder / p for p in names if RESULT.fullmatch(p)]
    if len(inputs) != expected_batches or len(results) != expected_batches:
        raise ImportWindowError("historic_import_batch_membership_changed")
    source_ids: set[str] = set()
    pages: set[tuple[str, int]] = set()
    excluded = imported = older_observations = reviewed = 0
    included_categories: set[str] = set()
    for key, path in inputs.items():
        source, doc = _read(path, 1_000_000)
        if hashlib.sha256(source).hexdigest() != key or doc.get("schema") != "sibur_archive_pages_v1":
            raise ImportWindowError("source_input_hash_or_schema_changed")
        if (not isinstance(doc.get("groups"), list)
                or not isinstance(doc.get("pages"), list)
                or not isinstance(doc.get("review"), list)
                or type(doc.get("older_rows")) is not int
                or doc["older_rows"] < 0):
            raise ImportWindowError("historical_selection_shape_changed")
        older_observations += doc["older_rows"]
        reviewed += len(doc["review"])
        imported += len(doc["groups"])
        for group in doc["groups"]:
            if not isinstance(group, dict) or not isinstance(group.get("external_id"), str):
                raise ImportWindowError("historical_group_identity_invalid")
            value = group["external_id"]
            if value in source_ids:
                raise ImportWindowError("duplicate_group_id_across_batches")
            source_ids.add(value)
        for item in doc["pages"]:
            cat, page = item.get("category"), item.get("page")
            if (cat not in CATEGORIES or cat == "999_19"
                    or type(page) is not int or page < 1 or page > 10000):
                raise ImportWindowError("unexpected_historical_import_category_or_page")
            if (cat, page) in pages:
                raise ImportWindowError("duplicate_historical_page_in_import_batches")
            pages.add((cat, page))
            included_categories.add(cat)
    matched_result_keys = set()
    for path in results:
        _, doc = _read(path, 80_000)
        source_hash = doc.get("source_input_sha256")
        if (not isinstance(source_hash, str) or HEX.fullmatch(source_hash) is None
                or source_hash not in inputs or source_hash in matched_result_keys):
            raise ImportWindowError("result_not_linked_to_exact_input")
        matched_result_keys.add(source_hash)
        result = doc.get("result")
        if not isinstance(result, dict) or not isinstance(doc.get("replay"), dict):
            raise ImportWindowError("historic_result_shape_invalid")
        _, input_doc = _read(inputs[source_hash], 1_000_000)
        if (result.get("older_rows_retained_privately") != input_doc["older_rows"]
                or type(result.get("inserted")) is not int
                or result["inserted"] < 0):
            raise ImportWindowError("historic_excluded_import_result_drift")
        excluded += result["older_rows_retained_privately"]
    if len(matched_result_keys) != len(inputs) or excluded != older_observations:
        raise ImportWindowError("input_result_historic_retention_inconsistent")
    return {
        "status": "PASS_HISTORICAL_IMPORT_SELECTION_ONLY",
        "batches_input_result": len(inputs),
        "original_pages_selected": len(pages),
        "included_categories": sorted(included_categories),
        "excluded_support_category": "999_19",
        "unique_selected_group_ids": len(source_ids),
        "group_observations_in_manifests": imported,
        "pre2024_source_observations_retained_privately": older_observations,
        "excluded_result_receipts": excluded,
        "review_rows_in_inputs": reviewed,
        "source_ids_exported": False,
        "retention_authority_granted": False,
        "external_source_requests": 0,
        "database_mutations": 0,
        "business_contract_acceptance": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saved-import-folder", required=True, type=Path)
    parser.add_argument("--expected-batches", type=int, default=166)
    args = parser.parse_args()
    if args.expected_batches < 1 or args.expected_batches > 2000:
        print('{"status":"blocked","error_code":"batch_limit_invalid"}')
        return 2
    try:
        report = audit_import_window(args.saved_import_folder, expected_batches=args.expected_batches)
    except (ImportWindowError, OSError, TypeError, ValueError, KeyError):
        print('{"status":"blocked","error_code":"historic_saved_source_receipt_drift"}')
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
