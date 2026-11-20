"""Inspect explicit existing daily targets. This command is read-only."""

from __future__ import annotations

import argparse
import json

from sqlalchemy import text

from src.modules.daily_tender_run.recovery_plan import RecoveryTarget, plan_target
from src.shared.db import models as _db_models  # noqa: F401
from src.shared.db.session import SessionLocal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--deal", required=True)
    parser.add_argument("--fingerprint", required=True)
    args = parser.parse_args()
    target = RecoveryTarget(args.run, args.registry, args.deal, args.fingerprint)
    with SessionLocal() as session:
        if session.get_bind().dialect.name != "postgresql":
            raise RuntimeError("Operator recovery plan requires PostgreSQL")
        session.execute(text("SET TRANSACTION READ ONLY"))
        try:
            plan = plan_target(session, target)
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        finally:
            session.rollback()


if __name__ == "__main__":
    main()
