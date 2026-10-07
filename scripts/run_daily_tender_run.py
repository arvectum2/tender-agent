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
    return parser


def main() -> int:
    args = _parser().parse_args()
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

        non_error_waits = {
            "WAITING_HUMAN",
            "WAITING_READINESS",
            "WAITING_SUBMISSION",
            "WAITING_OUTCOME",
            "COMPLETED",
        }
        resumed_ok = all(item.status in non_error_waits for item in resumed)
        if resumed_ok and response.status in non_error_waits:
            return 0
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
