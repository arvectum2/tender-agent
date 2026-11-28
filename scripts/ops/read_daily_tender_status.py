"""One read-only, aggregate latest DTR status for local operators.

No run creation, retry, downloads, ETP, customer details or source bytes.
The production PostgreSQL transaction is explicitly REPEATABLE READ READ ONLY.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

_PROFILE = "arvectum-it"
_PROFILES = (_PROFILE, "arvectum-it-223")
_RUN_ID = re.compile(r"DTR-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\Z")
_RUN_STATUSES = frozenset({
    "PENDING", "RUNNING", "WAITING_HUMAN", "WAITING_READINESS",
    "WAITING_SUBMISSION", "WAITING_OUTCOME", "COMPLETED_WITH_ERRORS",
    "COMPLETED",
})
_STAGES = frozenset({
    "DISCOVER", "DEDUPE", "SCREEN", "ACQUIRE_DOCS",
    "INDEX_DATA_PLATFORM", "ANALYZE", "SUMMARIZE", "WAIT_HUMAN",
    "POST_DECISION", "TRACK_SUBMISSION", "TRACK_OUTCOME",
    "DONE", "FAILED",
})
_ITEM_STATUSES = frozenset({
    "DISCOVERED", "SHORTLISTED", "SCREENED_OUT", "DUPLICATE",
    "PROCESSING", "MANAGER_READY", "FAILED", "POST_DECISION",
    "DEFERRED", "HUMAN_GO",
    "HUMAN_NO_GO", "READINESS_BLOCKED", "POST_DECISION_FAILED",
    "AWAITING_SUBMISSION_EVIDENCE", "AWAITING_OUTCOME_EVIDENCE",
    "OUTCOME_RECORDED",
})


def _utc(value: object) -> str | None:
    if not isinstance(value, datetime):
        return None
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _label(value: object, allowed: frozenset[str]) -> str:
    return value if isinstance(value, str) and value in allowed else "OTHER"


def make_snapshot(run: dict | None, items: list[dict], *, now: datetime | None = None, profile: str = _PROFILE) -> dict:
    """Project strictly approved structured fields; never include source payloads."""
    if profile not in _PROFILES:
        raise ValueError("Unsupported profile")
    if run is None:
        return {"scope": profile, "status": "NO_RUN", "item_counts": {}}
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware reference required")
    status_counts: dict[str, int] = defaultdict(int)
    last_change = run.get("updated_at")
    for item in items:
        status = _label(item.get("status"), _ITEM_STATUSES)
        count = item.get("item_count")
        if type(count) is not int or count < 0:
            raise ValueError("Invalid aggregate count")
        status_counts[status] += count
        updated = item.get("latest_change")
        if isinstance(updated, datetime) and (
            not isinstance(last_change, datetime) or updated > last_change
        ):
            last_change = updated
    age = None
    if isinstance(last_change, datetime):
        event = last_change.replace(tzinfo=UTC) if last_change.tzinfo is None else last_change.astimezone(UTC)
        age = max(0, int((now.astimezone(UTC) - event).total_seconds() // 60))
    run_id = run.get("run_id")
    return {
        "scope": profile,
        "run_id": run_id if isinstance(run_id, str) and _RUN_ID.fullmatch(run_id) else "REDACTED",
        "status": _label(run.get("status"), _RUN_STATUSES),
        "stage": _label(run.get("current_stage"), _STAGES),
        "run_started_utc": _utc(run.get("started_at")),
        "last_record_change_utc": _utc(last_change),
        "minutes_since_last_record_change": age,
        "error_present": bool(
            run.get("has_error") or run.get("status") == "COMPLETED_WITH_ERRORS"
            or status_counts.get("FAILED", 0) or status_counts.get("POST_DECISION_FAILED", 0)
        ),
        "item_counts": dict(sorted(status_counts.items())),
        "items_total": sum(status_counts.values()),
    }


def read_snapshot(engine, *, now: datetime | None = None, profile: str = _PROFILE) -> dict:
    if profile not in _PROFILES:
        raise ValueError("Unsupported profile")
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Production read-only status requires PostgreSQL")
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        try:
            identity = connection.execute(text(
                "SELECT current_database() AS database_name, current_user AS role_name"
            )).mappings().first()
            if not identity or identity["database_name"] != "arvectum" or identity["role_name"] != "arvectum":
                raise RuntimeError("Unexpected database identity")
            run_result = connection.execute(text("""
                SELECT run_id, status, current_stage, started_at, updated_at,
                       (error_summary IS NOT NULL AND error_summary <> '') AS has_error
                  FROM daily_tender_runs
                 WHERE profile_id = :profile
              ORDER BY created_at DESC, id DESC LIMIT 1
            """), {"profile": profile})
            run = run_result.mappings().first()
            items: list[dict] = []
            if run:
                items_result = connection.execute(text("""
                    SELECT status, count(*) AS item_count,
                           max(updated_at) AS latest_change
                      FROM daily_tender_run_items
                     WHERE run_id = :run_id
                  GROUP BY status
                """), {"run_id": run["run_id"]})
                items = list(items_result.mappings().all())
            return make_snapshot(run, items, now=now, profile=profile)
        finally:
            connection.rollback()


def main(argv: tuple[str, ...] | list[str] = ()) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=_PROFILES, default=_PROFILE)
    args = parser.parse_args(argv)
    try:
        from src.shared.db.session import engine

        report = read_snapshot(engine, profile=args.profile)
    except (OSError, RuntimeError, ValueError, TypeError, SQLAlchemyError):
        # No traceback, DB URL, SQL, source URL or private error text in CLI output.
        print("DTR_READONLY_STATUS_UNAVAILABLE", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
