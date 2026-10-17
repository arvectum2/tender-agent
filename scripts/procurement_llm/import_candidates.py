"""Operator-only controlled intake into the ALREADY EXISTING PostgreSQL arvectum.

Defaults to validation/dry-run. --apply requires explicitly configured PG URL
and completed Alembic migration. Never copies raw tender files, never trains.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from src.modules.procurement_learning_corpus.legacy_report import (
    make_unlinked_legacy_report_candidate,
)
from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.modules.procurement_learning_corpus.service import (
    append_candidate,
    make_analysis_candidate,
    make_legacy_candidate,
    make_manual_candidate,
    validate_candidate,
)
from src.tender_research.models import TenderAnalysisRun


def _legacy_items(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError("Private frozen SQLite evidence file missing")
    db = sqlite3.connect("file:" + str(path.resolve()) + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        rows = [
            dict(row) for row in db.execute(
                "SELECT observation_id, kind, procurement_ref, participation, review_state, "
                "provenance_sha256, candidate_split, training_status, payload "
                "FROM observations ORDER BY observation_id"
            )
        ]
    finally:
        db.close()
    results = [make_legacy_candidate(row) for row in rows]
    if len(results) != len({row["observation_id"] for row in results}):
        raise ValueError("Duplicate historical identity")
    return results


def _manual_items(path: Path) -> list[dict]:
    content = json.loads(path.read_text(encoding="utf-8"))
    return _manual_payload_items(content)


def _manual_payload_items(content: object) -> list[dict]:
    if not isinstance(content, dict):
        raise TypeError("Manual file must be JSON object")
    if "items" in content:
        if content.get("schema") != "manual-candidate-import-v1":
            raise ValueError("Unexpected manual batch format")
        items = content["items"]
    else:
        items = [content]
    if not isinstance(items, list) or not 1 <= len(items) <= 1000:
        raise ValueError("1-1000 manual events expected")
    return [make_manual_candidate(entry) for entry in items]


def _engine_url() -> str:
    from src.shared.config.settings import get_settings

    url = os.environ.get("AI_CORP_DATABASE_URL") or get_settings().database_url
    parsed = make_url(url)
    if not parsed.drivername.startswith("postgresql") or parsed.database != "arvectum":
        raise ValueError("Only existing PostgreSQL database 'arvectum' is permitted for apply")
    return url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--legacy-sqlite", type=Path)
    group.add_argument("--manual-file", type=Path)
    group.add_argument("--manual-stdin", action="store_true", help="Read JSON review from stdin; no intermediate file")
    group.add_argument("--legacy-report-file", action="append", type=Path, help="SHA-bound original report in existing ArvectumSSD data/rag/reports")
    parser.add_argument("--expected-report-sha256", action="append", help="Match 64-hex SHA256 for each --legacy-report-file")
    group.add_argument("--backfill-existing-runs", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Write candidates after reviewed migration")
    parser.add_argument("--confirm-database", choices=["arvectum"])
    args = parser.parse_args(argv)
    if args.apply and args.confirm_database != "arvectum":
        parser.error("--apply requires --confirm-database arvectum")
    if args.legacy_sqlite:
        items = _legacy_items(args.legacy_sqlite)
    elif args.manual_file:
        items = _manual_items(args.manual_file)
    elif args.legacy_report_file:
        if len(args.legacy_report_file) > 100 or len(args.legacy_report_file) != len(args.expected_report_sha256 or []):
            parser.error("1-100 legacy report paths, each with paired --expected-report-sha256, required")
        items = [
            make_unlinked_legacy_report_candidate(path, expected_sha256=expected)
            for path, expected in zip(args.legacy_report_file, args.expected_report_sha256)
        ]
    elif args.manual_stdin:
        if sys.stdin.isatty():
            parser.error("--manual-stdin requires piped JSON data")
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            parser.error("Manual review JSON exceeds 64 KiB")
        items = _manual_payload_items(json.loads(raw.decode("utf-8")))
    else:
        items = []
    for item in items:
        validate_candidate(item)
    if not args.apply and not args.backfill_existing_runs:
        print(json.dumps({"mode": "dry_run", "candidates": len(items), "unique_ids": len({r["observation_id"] for r in items})}))
        return 0

    engine = create_engine(_engine_url(), future=True)
    try:
        if not inspect(engine).has_table(ProcurementLearningObservation.__tablename__):
            raise RuntimeError("Migration 107 not installed in existing arvectum PostgreSQL. Refusing writes.")
        with Session(engine) as session, session.begin():
            if args.backfill_existing_runs:
                runs = session.scalars(select(TenderAnalysisRun).order_by(TenderAnalysisRun.id)).all()
                items = [make_analysis_candidate(run) for run in runs]
            count = sum(append_candidate(session, item) for item in items) if args.apply else 0
            if not args.apply:
                session.rollback()
        print(json.dumps({
            "mode": "applied" if args.apply else "db_read_only",
            "candidates": len(items), "inserted": count,
            "existing": len(items) - count if args.apply else None,
            "target": "existing_postgresql_arvectum",
        }))
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
