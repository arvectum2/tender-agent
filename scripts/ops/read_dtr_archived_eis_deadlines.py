"""Offline archived-only deadline evidence for a specific existing DTR.

No network access, new EIS request, new DTR, database write or human decision.
The intended PostgreSQL database and role are both arvectum; the
transaction is explicitly REPEATABLE READ READ ONLY and has no DML/DDL operations.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.modules.daily_tender_run.eis_archived_deadline import (
    ArchivedDeadlineError,
    verify_archived_deadline,
)
from src.modules.daily_tender_run.eis_detail_deadline import RUN_ID_RE
from src.shared.db.session import engine

MAX_ROWS = 12
_PROFILE = "arvectum-it"
SELECT_EVIDENCE = text(
    """
    SELECT i.registry_number, i.law AS item_law, i.deadline_at AS stored_dtr_deadline,
           t.law_type, a.artifact_type, a.source, a.local_path, a.sha256,
           a.size_bytes, a.raw_meta, a.created_at
    FROM daily_tender_run_items i
    JOIN daily_tender_runs r ON r.run_id = i.run_id
    LEFT JOIN procurement_tenders t ON t.registry_number = i.registry_number
    LEFT JOIN procurement_raw_artifacts a ON a.tender_id = t.id
      AND a.artifact_type = :artifact_type
    WHERE i.run_id = :run_id AND i.status = :item_status
      AND r.profile_id = :profile
    ORDER BY i.registry_number, a.created_at DESC
    LIMIT 13
    """
)


def build_archived_evidence(
    run_id: str,
    rows: list[dict[str, Any]],
    root: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    if (not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id)
            or not 0 < len(rows) <= MAX_ROWS):
        raise ArchivedDeadlineError("archive_unverified")
    registries = [row.get("registry_number") for row in rows]
    if any(not isinstance(value, str) for value in registries) or any(
        count != 1 for count in Counter(registries).values()
    ):
        raise ArchivedDeadlineError("archive_unverified")
    records = []
    for row in rows:
        if row.get("item_law") != "44fz":
            raise ArchivedDeadlineError("archive_unverified")
        proof = verify_archived_deadline(
            root, row["registry_number"], row, now=now,
        )
        records.append({
            "registry_number": proof.registry_number,
            "source_status": proof.source_status,
            "archived_deadline_utc": proof.archived_deadline_utc.isoformat(),
            "official_timezone": proof.official_timezone,
            "artifact_sha256": proof.artifact_sha256,
            "artifact_registered_utc": proof.artifact_registered_utc.isoformat(),
            "stored_dtr_deadline_present": row["stored_dtr_deadline"] is not None,
            "current_revision_verified": False,
        })
    return {
        "contract": "ta-dtr-archived-eis-deadline-v1",
        "run_id": run_id,
        "source_status": "ARCHIVED_ONLY",
        "records": records,
        "read_only": True,
        "source_network_requests": 0,
        "database_mutations": 0,
        "current_revision_verified": False,
        "generated_at_utc": (now or datetime.now(UTC)).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    args = parser.parse_args(argv)
    if not RUN_ID_RE.fullmatch(args.run_id) or not args.archive_root.is_absolute():
        print("ARCHIVED_EIS_UNVERIFIED", file=sys.stderr)
        return 2
    try:
        if engine.dialect.name != "postgresql":
            raise ArchivedDeadlineError("archive_unverified")
        with engine.connect() as connection:
            try:
                connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
                identity = connection.execute(text(
                    "SELECT current_database() AS database_name, current_user AS role_name"
                )).mappings().first()
                if (not identity or identity["database_name"] != "arvectum"
                        or identity["role_name"] != "arvectum"):
                    raise ArchivedDeadlineError("archive_unverified")
                rows = [
                    dict(row) for row in connection.execute(
                        SELECT_EVIDENCE,
                        {
                            "run_id": args.run_id,
                            "item_status": "MANAGER_READY",
                            "artifact_type": "public_detail_common_info",
                            "profile": _PROFILE,
                        },
                    ).mappings()
                ]
                evidence = build_archived_evidence(args.run_id, rows, args.archive_root)
            finally:
                connection.rollback()
        print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, SQLAlchemyError):
        print("ARCHIVED_EIS_UNVERIFIED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
