"""Read-only PG17 schema127 physical-base and isolated-clone receipt audit.

An exact archived WAL recovery target and a continuous seven-day PITR window
are NOT proved by a successful base backup or a standalone clone. The tool
never accesses PostgreSQL, Docker, EIS, or live services, and never writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any


class BackupEvidenceError(ValueError):
    """Fail closed without surfacing backup paths or private receipt payloads."""


def _json_receipt(path: Path) -> dict[str, Any]:
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= 64_000):
        raise BackupEvidenceError("receipt_missing_or_unsafe")
    try:
        data = json.loads(path.read_bytes())
    except (ValueError, UnicodeError, OSError) as exc:
        raise BackupEvidenceError("receipt_unreadable") from exc
    if not isinstance(data, dict):
        raise BackupEvidenceError("receipt_invalid")
    return data


def _physical_base(receipt_path: Path, receipt: dict[str, Any]) -> tuple[Path, str]:
    if receipt.get("status") != "pass" or receipt.get("live_database_mutated") is not False:
        raise BackupEvidenceError("base_receipt_not_verified")
    base_value = receipt.get("base_path")
    if not isinstance(base_value, str):
        raise BackupEvidenceError("base_path_missing")
    base = Path(base_value)
    if (not base.is_absolute() or base.is_symlink() or base.parent.is_symlink()
            or base.parent != receipt_path.parent or base.name != "data"
            or not base.is_dir()):
        raise BackupEvidenceError("base_path_not_bound_to_receipt")
    pg_version = base / "PG_VERSION"
    manifest = base / "backup_manifest"
    if (pg_version.is_symlink() or not pg_version.is_file() or pg_version.stat().st_size > 16
            or manifest.is_symlink() or not manifest.is_file()
            or not 0 < manifest.stat().st_size <= 10_000_000):
        raise BackupEvidenceError("backup_metadata_missing_or_unsafe")
    major = pg_version.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[0-9]{1,2}", major) or major != "17":
        raise BackupEvidenceError("unsupported_backup_major_version")
    # Do not expose manifest contents or local path. File-level integrity is
    # independently checked below by the matching-major pg_verifybackup.
    return base, hashlib.sha256(manifest.read_bytes()).hexdigest()


def _matched_receipts(source: dict[str, Any], clone: dict[str, Any], base: Path) -> dict:
    system_id = source.get("source_system_identifier")
    rows = clone.get("databases")
    if (not isinstance(system_id, str) or not re.fullmatch(r"[0-9]{10,30}", system_id)
            or source.get("manifest_verified") != "backup successfully verified"
            or not isinstance(source.get("isolated_same_image_restore"), dict)
            or source["isolated_same_image_restore"].get("system_identifier") != system_id
            or source["isolated_same_image_restore"].get("database") != "arvectum_data"
            or clone.get("status") != "pass" or clone.get("production_write") is not False
            or clone.get("network_none") is not True
            or clone.get("source_mount_readonly") is not True
            or clone.get("pg_verifybackup_pass") is not True
            or clone.get("integrated_wal_base_verified") is not True
            or clone.get("source_system_identifier") != system_id
            or clone.get("physical_source_base") != base.parent.name
            or clone.get("postrelease_business_schema127_physical_restored") is not True
            or clone.get("exact_archived_postbase_restore_target_tested") is not False
            or clone.get("continuous_7day_pitr_proven") is not False
            or not isinstance(rows, list) or len(rows) != 2):
        raise BackupEvidenceError("cluster_or_clone_receipt_mismatch")
    db = {row.get("database"): row for row in rows if isinstance(row, dict)}
    if set(db) != {"arvectum", "arvectum_data"}:
        raise BackupEvidenceError("expected_databases_missing")
    business, dp = db["arvectum"], db["arvectum_data"]
    if (business.get("system_identifier") != system_id
            or dp.get("system_identifier") != system_id
            or business.get("revision") != "127_private_review_link_corrections"
            or not isinstance(business.get("tenders"), int)
            or business["tenders"] < 64
            or not isinstance(business.get("new_tables"), int)
            or business["new_tables"] != 7
            or not isinstance(dp.get("collections"), int)
            or dp["collections"] < 73
            or business.get("recovery") is not False
            or dp.get("recovery") is not False):
        raise BackupEvidenceError("schema127_or_dp_clone_receipt_mismatch")
    return {"business_revision": business["revision"], "business_tenders": business["tenders"],
            "dp_collections": dp["collections"], "same_physical_cluster": True}


def audit(
    source_receipt: Path,
    physical_clone_receipt: Path,
    pg_verifybackup_binary: Path,
    *,
    runner: Callable = subprocess.run,
) -> dict:
    source = _json_receipt(source_receipt)
    clone = _json_receipt(physical_clone_receipt)
    base, manifest_sha = _physical_base(source_receipt, source)
    facts = _matched_receipts(source, clone, base)
    if (not pg_verifybackup_binary.is_absolute() or pg_verifybackup_binary.is_dir()
            or not pg_verifybackup_binary.is_file()):
        raise BackupEvidenceError("matching_major_verifier_missing")
    try:
        version = runner([str(pg_verifybackup_binary), "--version"],
                         capture_output=True, text=True, timeout=10)
        if version.returncode != 0 or not re.search(
            r"pg_verifybackup \(PostgreSQL\) 17\.[0-9]+(?:\.[0-9]+)?(?:\s|$)",
            version.stdout or "",
        ):
            raise BackupEvidenceError("backup_verifier_major_mismatch")
        verified = runner([str(pg_verifybackup_binary), "--no-parse-wal", str(base)],
                          capture_output=True, text=True, timeout=180)
        if verified.returncode != 0:
            raise BackupEvidenceError("backup_file_integrity_not_verified")
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise BackupEvidenceError("backup_verification_unavailable") from exc
    return {
        "contract": "ta-pitr127-readonly-postrelease-base-audit-v1",
        "read_only": True,
        "production_writes": 0,
        "database_queries": 0,
        "network_requests": 0,
        "postgresql_major": 17,
        "matching_version_pg_verifybackup": "PASS",
        "base_manifest_sha256": manifest_sha,
        "physical_backup_integrity": "VERIFIED",
        "independent_clone_receipt": "CONSISTENT",
        **facts,
        "archived_postbase_exact_wal_target": "NOT_PROVEN",
        "continuous_seven_day_pitr": "NOT_PROVEN",
        "production_recovery_acceptance": "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--clone-receipt", type=Path, required=True)
    parser.add_argument("--pg-verifybackup", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args.source_receipt, args.clone_receipt, args.pg_verifybackup)
    except BackupEvidenceError as exc:
        print(json.dumps({"contract": "ta-pitr127-readonly-postrelease-base-audit-v1",
                          "physical_backup_integrity": "NOT_PROVEN",
                          "continuous_seven_day_pitr": "NOT_PROVEN",
                          "error_code": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
