#!/usr/bin/env python3
"""Run and resume the durable Daily Tender workflow on the Mac mini.

This command is safe for unattended scheduling: it first resumes open runs so
human-decided cases can advance through local readiness and evidence tracking,
then starts the current discovery run. It never submits or modifies an
application, logs in to an ETP, signs, pays, sends supplier mail, or makes the
manager's GO/NO GO/DEFER choice.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.daily_tender_run.schemas import StartDailyTenderRunRequest
from src.modules.daily_tender_run.service import (
    create_daily_tender_run,
    resume_pending_daily_tender_runs,
    to_run_response,
)
from src.shared.db import models as _db_models  # noqa: F401
from src.shared.db.session import SessionLocal


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Daily Tender discovery and analysis")
    parser.add_argument("--profile", default="arvectum-it")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--company-schedule-tick", action="store_true", help="Run only one bounded opt-in company discovery tick")
    return parser


_NON_ERROR_WAITS = frozenset({
    "WAITING_HUMAN",
    "WAITING_READINESS",
    "WAITING_SUBMISSION",
    "WAITING_OUTCOME",
    "COMPLETED",
})
_SAFE_RUN_ID = re.compile(r"DTR-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\Z")
_SAFE_STATUS = re.compile(r"[A-Z_]{2,40}\Z")
_MAX_UNRESOLVED_SUMMARIES = 8


def _safe_diagnostic_value(value: object, *, run_id: bool = False) -> str:
    if not isinstance(value, str):
        return "REDACTED"
    pattern = _SAFE_RUN_ID if run_id else _SAFE_STATUS
    return value if pattern.fullmatch(value) else "REDACTED"


def _exit_code_with_diagnostic(resumed: list[object], current: object) -> int:
    """Preserve failure exit semantics while identifying old vs new errors safely.

    Never echo raw errors, original documents, customer metadata or URLs.
    This is a purely local CLI result check; it does not retry source work.
    """
    def clean(run: object) -> bool:
        return run.status in _NON_ERROR_WAITS and not run.error_summary

    unresolved = [run for run in resumed if not clean(run)]
    if not unresolved and clean(current):
        return 0
    summary = {
        "event": "DTR_EXIT20",
        "current_run": _safe_diagnostic_value(
            getattr(current, "run_id", None), run_id=True
        ),
        "current_status": _safe_diagnostic_value(getattr(current, "status", None)),
        "current_error": not clean(current),
        "unresolved_resumed_count": len(unresolved),
        "unresolved_resumed": [
            {
                "run_id": _safe_diagnostic_value(
                    getattr(run, "run_id", None), run_id=True
                ),
                "status": _safe_diagnostic_value(getattr(run, "status", None)),
                "error_present": bool(getattr(run, "error_summary", None)),
            }
            for run in unresolved[:_MAX_UNRESOLVED_SUMMARIES]
        ],
        "unresolved_resumed_truncated": max(
            0, len(unresolved) - _MAX_UNRESOLVED_SUMMARIES
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")), file=sys.stderr)
    return 20


def main() -> int:
    args = _parser().parse_args()
    if args.company_schedule_tick:
        from src.modules.saas_foundation.company_schedule import tick
        from src.shared.config.settings import get_settings

        with SessionLocal() as session:
            print(json.dumps(tick(session, get_settings()), ensure_ascii=False))
        return 0
    with SessionLocal() as session:
        resumed = resume_pending_daily_tender_runs(
            session,
            profile_id=args.profile,
            retry_failed=args.retry_failed,
        )
        run = create_daily_tender_run(
            session,
            StartDailyTenderRunRequest(
                profile_id=args.profile,
                run_now=True,
                retry_failed=args.retry_failed,
            ),
        )
        response = to_run_response(session, run)
        print(response.model_dump_json(indent=2))

        return _exit_code_with_diagnostic(resumed, response)


if __name__ == "__main__":
    raise SystemExit(main())
