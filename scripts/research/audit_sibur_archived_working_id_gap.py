"""Replay exact archived SIBUR original IDs against read-only PG16 working IDs.

Default validates original pages without DB. The optional working comparison
runs a hardcoded one-shot REPEATABLE READ READ ONLY SQL through local Docker
Unix socket. No network downloads, production PostgreSQL or DB writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from src.modules.tender_connectors.sibur.archive_parser import (
    CATEGORIES,
    replay_archived_page,
)

EXPECTED_CLUSTER = "7694400479046774822"
ARCHIVE_PROOF_SHA = "07c4ce310b28dec397aa927f9cbcbfaeb6d9374017038c03c2a59a0af25c7f0d"
GAP_PROOF_SHA = "069a8ce4fd0b6d74b6f3866df3116b9019c5cf0b13f1c45a198c76d2efd81085"
LIMIT_PAGES = 5000


class GapEvidenceError(ValueError):
    """Sanitized error codes only, never print raw original IDs or SQL."""


def digest_ids(ids) -> str:
    """Match prior proof encoding: sorted unique exact ID, newline-final UTF8."""
    return hashlib.sha256(("\n".join(sorted(ids)) + "\n").encode()).hexdigest()


def read_receipt(path: Path, expected_sha: str) -> dict:
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size < 200_000):
        raise GapEvidenceError("untrusted_saved_receipt")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise GapEvidenceError("saved_receipt_sha_changed")
    try:
        doc = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise GapEvidenceError("saved_receipt_unreadable") from exc
    if not isinstance(doc, dict):
        raise GapEvidenceError("invalid_saved_receipt")
    return doc


def replay_archive(root: Path, archive_receipt: dict, gap_receipt: dict) -> tuple[dict, int]:
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise GapEvidenceError("archive_directory_unsafe")
    prior = {x["category"]: x for x in archive_receipt["category_receipts"]}
    if set(prior) != set(CATEGORIES) or set(gap_receipt["categories"]) != set(CATEGORIES):
        raise GapEvidenceError("archive_category_membership_drift")
    by_category = {}
    all_observations = 0
    for category in CATEGORIES:
        directory = root / "categories" / category
        if category == "999_19":
            directory = root / "support-services-20261115" / category
        if directory.is_symlink() or not directory.is_dir():
            raise GapEvidenceError("archive_category_missing_or_link")
        head = replay_archived_page(directory, category, 1)
        count = head.last_page
        if not 0 < count <= LIMIT_PAGES:
            raise GapEvidenceError("archive_page_count_invalid")
        page_receipts = {int(x.name[1:6]) for x in directory.iterdir()
                         if re.fullmatch(r"p[0-9]{5}\.json", x.name)}
        if page_receipts != set(range(1, count + 1)):
            raise GapEvidenceError("archive_page_membership_drift")
        ids = set()
        member_hash = hashlib.sha256()
        observations = 0
        for number in range(1, count + 1):
            page = replay_archived_page(directory, category, number)
            if page.last_page != count:
                raise GapEvidenceError("archive_pagination_drift")
            member_hash.update(
                category.encode() + b":" + str(number).encode() + b":"
                + page.sha256.encode() + b"\n"
            )
            for row in page.records:
                ids.add(row["external_id"])
                observations += 1
        prev, matched = prior[category], gap_receipt["categories"][category]
        if (prev["member_aggregate_sha256"] != member_hash.hexdigest()
                or prev["receipt_page_count"] != count
                or prev["rows_in_replayed_pages"] != observations
                or matched["unique"] != len(ids)
                or matched["duplicate_observations"] != observations - len(ids)):
            raise GapEvidenceError("archive_original_row_drift")
        by_category[category] = ids
        all_observations += observations
        print("ARCHIVE_CATEGORY_PASS", category, "pages", count, "unique", len(ids), flush=True)
    union = set().union(*by_category.values())
    if (all_observations != gap_receipt["archived_observations"]
            or len(union) != gap_receipt["archived_unique_ids"]
            or digest_ids(union) != gap_receipt["source_archive_unique_ids_sha256"]):
        raise GapEvidenceError("archive_full_identity_drift")
    return by_category, all_observations


# Fixed PG16 local research container, no TCP, passwords or customer data
# exported. Query is *only* a single repeatable-read read-only transaction.
SOURCE_SQL = (
    "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;"
    " SELECT json_build_object("
    "'sid',(SELECT system_identifier::text FROM pg_control_system()),"
    "'readonly',current_setting('transaction_read_only'),"
    "'ids',(SELECT json_agg(external_id ORDER BY external_id)"
    " FROM (SELECT DISTINCT external_id FROM procurement_tenders"
    " WHERE source='sibur_public') source_ids));"
    " ROLLBACK;"
)


def working_id_snapshot(gap_receipt: dict) -> set[str]:
    command = [
        "docker", "exec", "arvectum-local-e2e-db-1",
        "psql", "-X", "-q", "-A", "-t",
        "-U", "arvectum", "-d", "arvectum_local",
        "-v", "ON_ERROR_STOP=1", "-c", SOURCE_SQL,
    ]
    try:
        proc = subprocess.run(command, check=False, capture_output=True, text=True, timeout=40)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GapEvidenceError("readonly_working_db_unavailable") from exc
    if proc.returncode:
        raise GapEvidenceError("readonly_working_db_query_failed")
    rows = [line for line in proc.stdout.splitlines() if line.startswith("{")]
    if len(rows) != 1:
        raise GapEvidenceError("ambiguous_working_db_snapshot")
    try:
        parsed = json.loads(rows[0])
    except ValueError as exc:
        raise GapEvidenceError("invalid_working_snapshot") from exc
    if (parsed.get("sid") != EXPECTED_CLUSTER
            or parsed.get("sid") != gap_receipt["work_database_cluster_identifier"]
            or parsed.get("readonly") != "on"
            or not isinstance(parsed.get("ids"), list)
            or not all(isinstance(value, str) and value for value in parsed["ids"])):
        raise GapEvidenceError("wrong_working_cluster_or_not_readonly")
    ids = set(parsed["ids"])
    if (len(ids) != len(parsed["ids"])
            or len(ids) != gap_receipt["working_unique_source_ids"]
            or digest_ids(ids) != gap_receipt["working_database_ids_sha256"]):
        raise GapEvidenceError("working_source_id_set_drift")
    return ids


def summarize_gap(by_category: dict, working_ids: set[str], gap_receipt: dict) -> dict:
    original = set().union(*by_category.values())
    missing = original - working_ids
    extras = working_ids - original
    overlap = original & working_ids
    per_category = {key: len(value - working_ids) for key, value in by_category.items()}
    if (len(original) != gap_receipt["archived_unique_ids"]
            or len(working_ids) != gap_receipt["working_unique_source_ids"]
            or len(missing) != gap_receipt["missing_from_working"]
            or len(extras) != gap_receipt["working_not_in_archive"]
            or len(overlap) != gap_receipt["overlapping_ids"]
            or digest_ids(missing) != gap_receipt["missing_historical_ids_sha256"]
            or any(per_category[key] != gap_receipt["categories"][key]["missing_in_working"]
                   for key in by_category)):
        raise GapEvidenceError("independent_diff_disagrees_with_saved_receipt")
    return {
        "status": "PASS_HISTORICAL_IDENTITY_DIFF_ONLY",
        "originals": len(original), "working": len(working_ids),
        "overlap": len(overlap), "missing_historical": len(missing),
        "working_only": len(extras), "per_category_missing": per_category,
        "original_ids_sha256": digest_ids(original),
        "working_ids_sha256": digest_ids(working_ids),
        "missing_ids_sha256": digest_ids(missing),
        "matched_original_page_receipts": True,
        "working_db_repeatable_read_readonly": True,
        "working_db_cluster": EXPECTED_CLUSTER,
        "source_status_current_verified": False,
        "missing_ids_are_live_tenders": False,
        "gap_root_cause": "UNKNOWN",
        "mass_import_authorized": False,
        "production_mutations": 0,
    }


def proof_create_once(path: Path, report: dict) -> None:
    if (not path.is_absolute() or path.is_symlink()
            or not path.parent.is_dir() or path.parent.is_symlink()
            or path.exists()):
        raise GapEvidenceError("proof_destination_untrusted_or_exists")
    fd, temporary = tempfile.mkstemp(prefix=".sibur-gap-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(report, handle, sort_keys=True, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--archive-proof", type=Path, required=True)
    parser.add_argument("--gap-proof", type=Path, required=True)
    parser.add_argument("--with-working-db-readonly", action="store_true")
    parser.add_argument("--private-proof-output", type=Path)
    args = parser.parse_args()
    try:
        if args.with_working_db_readonly != (args.private_proof_output is not None):
            raise GapEvidenceError("private_proof_required_only_for_db_comparison")
        old = read_receipt(args.gap_proof, GAP_PROOF_SHA)
        archive = read_receipt(args.archive_proof, ARCHIVE_PROOF_SHA)
        if (old.get("status") != "historical_archive_coverage_gap_read_only"
                or old.get("source") != "sibur_public"
                or old.get("database_mutations") != 0
                or old.get("network_requests") != 0
                or old.get("source_import_authorized") is not False
                or old.get("source_archive_full_original_proof_sha256") != ARCHIVE_PROOF_SHA
                or archive.get("status") != "pass_historical_source_window"):
            raise GapEvidenceError("saved_evidence_status_not_admissible")
        by_category, observations = replay_archive(args.archive_root, archive, old)
        output = {
            "archive_only": "PASS",
            "working_comparison": "NOT_EXECUTED",
            "pages_replayed": archive["verified_original_page_count"],
            "archive_observations": observations,
            "archive_unique_ids": len(set().union(*by_category.values())),
            "source_status_current_verified": False,
            "gap_root_cause": "UNKNOWN",
            "production_mutations": 0,
        }
        if args.with_working_db_readonly:
            working = working_id_snapshot(old)
            output.update(summarize_gap(by_category, working, old))
            output["working_comparison"] = "PASS"
            output["pages_replayed"] = archive["verified_original_page_count"]
            output["archive_observations"] = observations
            proof_create_once(args.private_proof_output, output)
    except GapEvidenceError as exc:
        print(json.dumps({"status": "BLOCKED", "error_code": str(exc)}))
        return 2
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"status": "BLOCKED", "error_code": "original_evidence_or_receipt_validation_failed"}))
        return 2
    print(json.dumps(output, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
