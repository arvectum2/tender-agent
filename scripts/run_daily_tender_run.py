#!/usr/bin/env python3
"""Run the durable Daily Tender workflow on the Mac mini.

This command is safe for unattended scheduling: it reads public procurement
sources, writes internal Tender Agent/Data Platform state and reports, and
stops at WAIT_HUMAN. It never submits an application, logs in to an ETP,
signs, pays, sends supplier mail, or makes the manager's GO/NO GO/DEFER choice.
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
        if response.status in {"WAITING_HUMAN", "COMPLETED"}:
            return 0
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
