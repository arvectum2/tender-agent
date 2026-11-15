"""Append novel source identities; retain conflicting archive observations in private receipts."""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime

from scripts.research.import_sibur_public_snapshot import SOURCE, build_rows


def separate(rows, existing):
    novel, exact, changed = [], [], []
    for row in rows:
        key = row["external_id"]
        old = existing.get(key)
        if old is None:
            novel.append(row)
        elif old == row["content_hash"]:
            exact.append(key)
        else:
            changed.append({"external_id": key, "prior_hash": old, "incoming_hash": row["content_hash"]})
    return novel, exact, changed


def apply(session, payload):
    from sqlalchemy import func, select
    from sqlalchemy.dialects.postgresql import insert

    from src.tender_research.models import ProcurementTender

    if payload.get("schema") != "sibur_archive_pages_v1":
        raise ValueError("unexpected archive schema")
    groups = payload["groups"]
    if len(groups) > 600:
        raise ValueError("bounded import batch required")
    rows = build_rows(groups, archive=True)
    if any(r["publication_date"] is None or r["publication_date"].date().isoformat() < "2024-01-01" for r in rows):
        raise ValueError("outside selected publication scope")
    table = ProcurementTender.__table__
    where = table.c.source == SOURCE
    before = session.execute(select(func.count()).select_from(table).where(where)).scalar_one()
    existing = dict(session.execute(select(table.c.external_id, table.c.content_hash)
                                    .where(where, table.c.external_id.in_([r["external_id"] for r in rows]))).all())
    novel, exact, changed = separate(rows, existing)
    for row in novel:
        result = session.execute(insert(table).values(**row).on_conflict_do_nothing(
            index_elements=["source", "external_id"]).returning(table.c.id))
        if result.scalar_one_or_none() is None:
            raise ValueError("concurrent source insertion")
    actual = dict(session.execute(select(table.c.external_id, table.c.content_hash).where(
        where, table.c.external_id.in_([r["external_id"] for r in rows]))).all())
    if any(actual.get(r["external_id"]) != r["content_hash"] for r in novel):
        raise ValueError("inserted source hash mismatch")
    if any(actual.get(k) != v for k, v in existing.items()):
        raise ValueError("prior source observation was overwritten")
    after = session.execute(select(func.count()).select_from(table).where(where)).scalar_one()
    if after-before != len(novel):
        raise ValueError("archive count mismatch")
    return {"inserted": len(novel), "exact_replay": len(exact), "existing_changed":len(changed),
            "changed":changed, "before":before, "after":after,
            "pages":payload["pages"], "older_rows_retained_privately":payload["older_rows"],
            "verified_at":datetime.now(UTC).isoformat()}


def main():
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    engine = create_engine(os.environ["AI_CORP_DATABASE_URL"])
    with Session(engine) as session, session.begin():
        if session.execute(text("select current_database()")).scalar_one() != "arvectum_local":
            raise ValueError("unexpected DB")
        result = apply(session,json.load(sys.stdin))
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
